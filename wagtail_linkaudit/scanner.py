"""
Synchronous link scanner - no task queue required.

This module provides a simple synchronous scanner that can be run
from a management command or cron job.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

from django.db import IntegrityError
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import Scan, URL, BrokenLink, WhitelistedDomain, WhitelistedURL
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


def run_scan(start_url, max_pages=500, max_depth=3):
    """
    Run a complete link audit scan synchronously.
    
    Args:
        start_url: The starting URL to crawl from
        max_pages: Maximum number of pages to scan
        max_depth: Maximum crawl depth
    
    Returns:
        Scan object with results
    """
    # Create scan
    scan = Scan.objects.create(
        max_pages=max_pages,
        max_depth=max_depth,
        status='running',
        started_at=timezone.now()
    )
    
    print(f"Starting scan {scan.id} from {start_url}")
    
    # Queue of (url, depth) tuples to process
    to_crawl = deque([(start_url, 0)])
    visited = set()
    
    while to_crawl and scan.pages_scanned < max_pages:
        url, depth = to_crawl.popleft()
        
        # Skip if already visited
        if url in visited:
            continue
            
        # Skip if exceeds depth
        if depth > max_depth:
            continue
        
        visited.add(url)
        url = normalize_url(url)
        
        # Check if URL was already saved
        if URL.objects.filter(scan=scan, url=url).exists():
            continue
        
        # Crawl the page
        print(f"Scanning [{scan.pages_scanned + 1}/{max_pages}] depth={depth}: {url[:80]}")
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            status_code = response.status_code
            content = response.text if status_code == 200 else None
        except requests.RequestException as e:
            print(f"  ✗ Error: {e}")
            status_code = None
            content = None
        
        # Save URL
        try:
            URL.objects.create(
                scan=scan,
                url=url,
                status_code=status_code,
                is_broken=(status_code is None or status_code >= 400),
            )
        except IntegrityError:
            continue
        
        # Increment counter
        scan.pages_scanned += 1
        scan.save(update_fields=['pages_scanned'])
        
        # Parse links if successful
        if status_code == 200 and content:
            soup = BeautifulSoup(content, "html.parser")
            
            for tag in soup.find_all("a", href=True):
                href = tag.get("href", "").strip()
                
                # Skip empty hrefs
                if not href:
                    continue
                
                # Skip invalid protocols
                href_lower = href.lower()
                if (href_lower.startswith("mailto:") 
                    or href_lower.startswith("tel:") 
                    or href_lower.startswith("javascript:")
                    or href_lower.startswith("#")):
                    continue
                
                # Create absolute URL
                absolute_url = normalize_url(urljoin(url, href))
                
                # Skip if invalid
                if not is_valid_link(absolute_url):
                    continue
                
                if should_skip(absolute_url):
                    continue
                
                # Internal links: add to crawl queue
                if is_internal(url, absolute_url):
                    if absolute_url not in visited:
                        to_crawl.append((absolute_url, depth + 1))
                else:
                    # External link: check it
                    check_external_link(scan, url, absolute_url)
    
    # Mark scan complete
    scan.status = 'completed'
    scan.finished_at = timezone.now()
    scan.save(update_fields=['status', 'finished_at'])
    
    print(f"\nScan complete! Checked {scan.pages_scanned} pages")
    print(f"Critical broken links: {scan.critical_broken_links_count}")
    print(f"Links needing review: {scan.needs_review_count}")
    
    # Send email notification
    send_scan_results_email(scan)
    
    return scan


def check_external_link(scan, source_url, target_url):
    """
    Check an external link and record if it's broken.
    """
    target_url = normalize_url(target_url)
    
    # Check if already checked
    if BrokenLink.objects.filter(scan=scan, target_url=target_url).exists():
        return
    
    # Check if domain is whitelisted
    domain = urlparse(target_url).netloc
    if WhitelistedDomain.objects.filter(domain=domain).exists():
        return
    
    # Check if URL is whitelisted
    for whitelisted_url in WhitelistedURL.objects.all():
        if whitelisted_url.matches(target_url):
            return
    
    # Check the link
    try:
        response = requests.head(target_url, headers=HEADERS, timeout=10, allow_redirects=True)
        status_code = response.status_code
    except requests.RequestException:
        try:
            response = requests.get(target_url, headers=HEADERS, timeout=10, allow_redirects=True)
            status_code = response.status_code
        except requests.RequestException:
            status_code = None
    
    # Record if broken
    is_broken = (status_code is None or status_code >= 400)
    
    if is_broken:
        # Skip bot-blocking domains for certain status codes
        if status_code in [400, 403] and domain in WHITELISTED_BOT_BLOCKING_DOMAINS:
            return
        
        try:
            BrokenLink.objects.create(
                scan=scan,
                source_url=source_url,
                target_url=target_url,
                status_code=status_code,
                review_status='new'
            )
            print(f"  ✗ Broken link: {target_url} ({status_code})")
        except IntegrityError:
            pass


def send_scan_results_email(scan):
    """Send email notification with scan results"""
    from wagtail.models import Site as WagtailSite
    
    # Get site information
    try:
        wagtail_site = WagtailSite.objects.filter(is_default_site=True).first()
        site_name = wagtail_site.site_name if wagtail_site else getattr(settings, 'WAGTAIL_SITE_NAME', 'Unknown Site')
        site_url = wagtail_site.root_url if wagtail_site else getattr(settings, 'BASE_URL', 'Unknown')
    except Exception:
        site_name = getattr(settings, 'WAGTAIL_SITE_NAME', 'Unknown Site')
        site_url = getattr(settings, 'BASE_URL', 'Unknown')
    
    # Get email recipients
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
    
    # Build email body
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
    
    # Subject line
    if critical_count > 0:
        subject = f"Link Audit: {critical_count} Critical Issue(s) Found - {site_name}"
    elif needs_review_count > 0:
        subject = f"Link Audit: {needs_review_count} Link(s) Need Review - {site_name}"
    else:
        subject = f"Link Audit Complete: No Issues - {site_name}"
    
    from_email = getattr(settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL", "webmaster@localhost")
    
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=False,
        )
        print(f"\n✓ Email sent to {', '.join(recipients)}")
    except Exception as e:
        print(f"\n✗ Failed to send email: {e}")


def cleanup_old_scans(days_to_keep=90):
    """
    Delete scans older than the specified number of days.
    Related URLs and BrokenLinks will be automatically deleted via CASCADE.
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    old_scans = Scan.objects.filter(started_at__lt=cutoff_date)
    count = old_scans.count()
    
    if count > 0:
        old_scans.delete()
        print(f"Deleted {count} scan(s) older than {days_to_keep} days")
        return count
    
    print(f"No scans older than {days_to_keep} days found")
    return 0
