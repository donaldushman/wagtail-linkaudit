"""
Link audit scanning functions.

This module contains the core scanning logic for checking links.
Functions are designed to be run synchronously (no task queue required).
Use the management command `python manage.py run_link_scan` to start a scan.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

from .models import Scan, URL, BrokenLink, WhitelistedDomain
from .utils import (
    is_valid_link,
    normalize_url,
    is_internal,
    should_skip,
)

# Browser-like headers to avoid 403 errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Domains that commonly block bots with 400/403 errors but are known to be valid
# Add domains (without http/https) that you want to exclude from bot-blocking error reporting
WHITELISTED_BOT_BLOCKING_DOMAINS = {
    'linkedin.com',
    'www.linkedin.com',
    'facebook.com',
    'www.facebook.com',
    'twitter.com',
    'x.com',
    'instagram.com',
    'www.instagram.com',
    'www.w3.org',
    'thenai.org',
    'youradchoices.com',
}


# -----------------------------
# Crawl a page
# -----------------------------
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def crawl_page(self, scan_id, url, depth=0):
    from django.db.models import F

    scan = Scan.objects.get(id=scan_id)

    # Stop if scan is already done
    if scan.status != "running":
        return

    # Depth limit
    if depth > scan.max_depth:
        return

    # Page limit
    if scan.pages_scanned >= scan.max_pages:
        mark_scan_complete(scan)
        return

    url = normalize_url(url)
    
    # Check if this URL was already processed (prevents duplicate work from race conditions)
    if URL.objects.filter(scan=scan, url=url).exists():
        return

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        status_code = response.status_code
    except requests.RequestException:
        status_code = None

    # Deduplicated save
    try:
        URL.objects.create(
            scan=scan,
            url=url,
            status_code=status_code,
            is_broken=(status_code is None or status_code >= 400),
        )
    except IntegrityError:
        return

    # Increment counter safely
    Scan.objects.filter(id=scan.id).update(
        pages_scanned=F("pages_scanned") + 1
    )

    # Reload updated value
    scan.refresh_from_db()

    # Stop if limit reached AFTER increment
    if scan.pages_scanned >= scan.max_pages:
        mark_scan_complete(scan)
        return

    if status_code != 200:
        return

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()

        # Skip empty hrefs
        if not href:
            continue

        # Skip invalid protocols and fragment-only links on raw href
        href_lower = href.lower()
        if (href_lower.startswith("mailto:") 
            or href_lower.startswith("tel:") 
            or href_lower.startswith("javascript:")
            or href_lower.startswith("#")):
            continue

        # Create absolute URL and normalize
        absolute_url = normalize_url(urljoin(url, href))

        # Skip if normalized URL is invalid
        if not is_valid_link(absolute_url):
            continue

        if should_skip(absolute_url):
            continue

        if is_internal(url, absolute_url):
            # Check if URL was already visited/queued before spawning new task
            # This prevents exponential task spawning
            if not URL.objects.filter(scan_id=scan_id, url=absolute_url).exists():
                crawl_page.delay(scan_id, absolute_url, depth + 1)
        else:
            # Check if external link was already checked before spawning new task
            # External URLs are now tracked in the URL table
            if not URL.objects.filter(scan_id=scan_id, url=absolute_url).exists():
                check_link.delay(scan_id, url, absolute_url)


# -----------------------------
# Check external link
# -----------------------------
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 1})
def check_link(self, scan_id, source_url, target_url):
    scan = Scan.objects.get(id=scan_id)
    
    # Stop if scan is no longer running
    if scan.status != "running":
        return

    # Safety check: skip invalid protocols (shouldn't reach here, but just in case)
    target_lower = target_url.lower()
    if (target_lower.startswith("mailto:") 
        or target_lower.startswith("tel:") 
        or target_lower.startswith("javascript:")
        or target_lower.startswith("#")):
        return
    
    # Check if we already checked this external URL (prevents duplicate checks from race conditions)
    if URL.objects.filter(scan=scan, url=target_url).exists():
        return

    try:
        response = requests.head(target_url, headers=HEADERS, allow_redirects=True, timeout=10)

        # fallback if HEAD not allowed
        if response.status_code == 405:
            response = requests.get(target_url, headers=HEADERS, timeout=10)

        status_code = response.status_code

    except requests.RequestException:
        status_code = None

    # Record the external URL check to prevent duplicate checks
    try:
        URL.objects.create(
            scan=scan,
            url=target_url,
            status_code=status_code,
            is_broken=(status_code is None or status_code >= 400),
        )
    except IntegrityError:
        # Already recorded by another task
        return

    # Only record broken links in the BrokenLink table for reporting
    if status_code is None or status_code >= 400:
        # Check if this domain is whitelisted
        domain = urlparse(target_url).netloc.lower()
        
        # Check database whitelist
        if WhitelistedDomain.objects.filter(domain=domain).exists():
            # Domain is whitelisted, skip recording broken link
            return
        
        # Also check hardcoded whitelist for known bot blockers
        if domain in WHITELISTED_BOT_BLOCKING_DOMAINS:
            # Known-good domain that blocks bots, skip recording
            return
        
        # Use get_or_create to avoid duplicate broken links for the same target
        try:
            BrokenLink.objects.get_or_create(
                scan=scan,
                target_url=target_url,
                defaults={
                    'source_url': source_url,
                    'status_code': status_code or 0,
                }
            )
        except IntegrityError:
            # Already exists from a parallel task
            pass

def mark_scan_complete(scan):
    if scan.status != "running":
        return

    scan.status = "completed"
    scan.finished_at = timezone.now()
    scan.save(update_fields=["status", "finished_at"])
    
    # Send email notification
    send_scan_results_email.delay(scan.id)


@shared_task
def check_scan_completion(scan_id, previous_page_count=0):
    """
    Check if a scan has stalled and should be marked complete.
    This is called periodically to catch scans that run out of pages
    before hitting the max_pages limit.
    """
    scan = Scan.objects.get(id=scan_id)
    
    # Skip if already finished
    if scan.status != "running":
        return
    
    # Check how long since the scan started
    runtime_minutes = (timezone.now() - scan.started_at).total_seconds() / 60
    current_page_count = scan.pages_scanned
    
    # If no progress in the last 2 minutes, consider it complete
    if runtime_minutes >= 2 and current_page_count == previous_page_count:
        # No progress, scan is done
        mark_scan_complete(scan)
        return
    
    # If scan has been running for more than 60 minutes, force complete
    if runtime_minutes > 60:
        mark_scan_complete(scan)
        return
    
    # Schedule another check in 2 minutes with current count
    check_scan_completion.apply_async(
        args=[scan_id, current_page_count], 
        countdown=120
    )


@shared_task
def send_scan_results_email(scan_id):
    """Send simplified email notification with link to admin"""
    from django.core.mail import send_mail
    from django.conf import settings
    from wagtail.models import Site as WagtailSite
    
    scan = Scan.objects.get(id=scan_id)
    
    # Get current site information
    try:
        wagtail_site = WagtailSite.objects.filter(is_default_site=True).first()
        site_name = wagtail_site.site_name if wagtail_site else settings.WAGTAIL_SITE_NAME
        site_url = wagtail_site.root_url if wagtail_site else getattr(settings, 'BASE_URL', 'Unknown')
    except Exception:
        site_name = getattr(settings, 'WAGTAIL_SITE_NAME', 'Unknown Site')
        site_url = getattr(settings, 'BASE_URL', 'Unknown')
    
    # Get email recipients from settings
    recipients = getattr(settings, 'LINKAUDIT_EMAIL_RECIPIENTS', [])
    if not recipients:
        recipients = [getattr(settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL", "webmaster@localhost")]
    
    # Get scan statistics
    total_urls = URL.objects.filter(scan=scan).count()
    critical_count = scan.critical_broken_links_count
    needs_review_count = scan.needs_review_count
    
    # Build admin URL
    admin_base = getattr(settings, 'WAGTAIL_ADMIN_URL', '/admin/')
    if not admin_base.endswith('/'):
        admin_base += '/'
    broken_links_url = f"{site_url}{admin_base}wagtail_linkaudit/brokenlink/?scan__id__exact={scan.id}"
    
    # Calculate duration
    duration = (scan.finished_at - scan.started_at).total_seconds() / 60 if scan.finished_at else 0
    
    # Check if scan hit the page limit
    hit_limit = scan.pages_scanned >= scan.max_pages
    pages_note = " (limit reached)" if hit_limit else ""
    
    # Build simple email body
    body = f"""Link Audit Scan Completed

Site: {site_name}
Duration: {duration:.1f} minutes
Pages Scanned: {scan.pages_scanned}{pages_note}
URLs Checked: {total_urls}

RESULTS:
"""
    
    if critical_count > 0:
        body += f"• {critical_count} CRITICAL issue(s) - Requires immediate attention (404, 400, 410 errors)\n"
    
    if needs_review_count > critical_count:
        investigate_count = needs_review_count - critical_count
        body += f"• {investigate_count} link(s) to investigate (403, 500, etc. - may be false positives)\n"
    
    if needs_review_count == 0:
        body += "✓ No broken links found!\n"
    
    body += f"\nView full details in the admin:\n{broken_links_url}\n"
    
    if hit_limit:
        body += f"\nNote: Scan stopped after reaching the maximum page limit of {scan.max_pages} pages.\n"
    
    # Simple subject line
    if critical_count > 0:
        subject = f"Link Audit: {critical_count} Critical Issue(s) Found - {site_name}"
    elif needs_review_count > 0:
        subject = f"Link Audit: {needs_review_count} Link(s) Need Review - {site_name}"
    else:
        subject = f"Link Audit Complete: No Issues - {site_name}"
    
    from_email = getattr(settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL", "webmaster@localhost")
    
    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=recipients,
        fail_silently=False,
    )


@shared_task
def cleanup_old_scans(days_to_keep=90):
    """
    Delete scans older than the specified number of days.
    
    This task can be scheduled to run periodically to keep the database clean.
    Related URLs and BrokenLinks will be automatically deleted via CASCADE.
    
    Args:
        days_to_keep: Number of days to retain scans (default: 90)
    
    Example Celery Beat schedule (add to settings):
        CELERY_BEAT_SCHEDULE = {
            'cleanup-old-scans': {
                'task': 'linkchecker.tasks.cleanup_old_scans',
                'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
                'kwargs': {'days_to_keep': 90},
            },
        }
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    old_scans = Scan.objects.filter(started_at__lt=cutoff_date)
    count = old_scans.count()
    
    if count > 0:
        old_scans.delete()
        return f"Deleted {count} scan(s) older than {days_to_keep} days"
    
    return f"No scans older than {days_to_keep} days found"