from django.db import models
from django.conf import settings


class EmailRecipient(models.Model):
    """Email addresses that should receive scan completion notifications
    
    Manage notification recipients via Wagtail admin. Emails from 
    LINKAUDIT_EMAIL_RECIPIENTS setting are always included.
    """
    email = models.EmailField(unique=True, help_text="Email address to receive scan notifications")
    name = models.CharField(max_length=255, blank=True, help_text="Name or description (optional)")
    is_active = models.BooleanField(default=True, help_text="Uncheck to temporarily disable notifications")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_recipients'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['email']
        verbose_name = "Email Recipient"
        verbose_name_plural = "Email Recipients"

    def __str__(self):
        if self.name:
            status = " (inactive)" if not self.is_active else ""
            return f"{self.name} <{self.email}>{status}"
        return self.email


class WhitelistedDomain(models.Model):
    """Domains that should be excluded from broken link reporting (e.g., known bot blockers)
    
    Note: Only accessible via Django admin (superusers only). Use WhitelistedURL for 
    content manager access via Wagtail admin.
    """
    domain = models.CharField(max_length=255, unique=True, help_text="Domain without protocol (e.g., linkedin.com)")
    reason = models.TextField(blank=True, help_text="Why this domain is whitelisted (e.g., 'Known to block bots')")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='whitelisted_domains'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['domain']
        verbose_name = "Whitelisted Domain"
        verbose_name_plural = "Whitelisted Domains"

    def __str__(self):
        return self.domain


class WhitelistedURL(models.Model):
    """Specific URLs that should be excluded from broken link reporting
    
    More granular than WhitelistedDomain - allows whitelisting individual URLs
    without hiding all links from that domain.
    """
    MATCH_TYPE_CHOICES = [
        ('exact', 'Exact URL only'),
        ('prefix', 'URL and all paths under it'),
    ]
    
    url = models.URLField(unique=True, help_text="Full URL to whitelist (e.g., https://example.com/page)")
    match_type = models.CharField(
        max_length=10,
        choices=MATCH_TYPE_CHOICES,
        default='exact',
        help_text="How to match this URL"
    )
    reason = models.TextField(blank=True, help_text="Why this URL is whitelisted")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='whitelisted_urls'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['url']
        verbose_name = "Whitelisted URL"
        verbose_name_plural = "Whitelisted URLs"

    def __str__(self):
        match_display = " (prefix)" if self.match_type == 'prefix' else ""
        return f"{self.url}{match_display}"
    
    def matches(self, url):
        """Check if this whitelist entry matches the given URL"""
        if self.match_type == 'exact':
            return self.url == url
        else:  # prefix
            return url.startswith(self.url)


class Scan(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="running",
    )
    max_pages = models.IntegerField(default=500)
    max_depth = models.IntegerField(default=3)
    pages_scanned = models.IntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Scan #{self.id} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def critical_broken_links_count(self):
        """Count of critical broken links (404, 400, 410, 0)"""
        return self.brokenlink_set.filter(
            status_code__in=[0, 400, 404, 410]
        ).exclude(review_status='whitelisted').count()

    @property
    def needs_review_count(self):
        """Count of links that need review (all except whitelisted and fixed)"""
        return self.brokenlink_set.exclude(
            review_status__in=['whitelisted', 'fixed']
        ).count()


class URL(models.Model):
    scan = models.ForeignKey(Scan, on_delete=models.CASCADE)
    url = models.URLField()
    status_code = models.IntegerField(null=True)
    is_broken = models.BooleanField(default=False)

    class Meta:
        unique_together = [['scan', 'url']]
        verbose_name = "URL"
        verbose_name_plural = "URLs"

    def __str__(self):
        return self.url


class BrokenLink(models.Model):
    REVIEW_STATUS_CHOICES = [
        ('new', 'New - Needs Review'),
        ('reviewing', 'Under Review'),
        ('whitelisted', 'Whitelisted'),
        ('fixed', 'Fixed'),
    ]

    scan = models.ForeignKey(Scan, on_delete=models.CASCADE)
    source_url = models.URLField()
    target_url = models.URLField()
    status_code = models.IntegerField()
    
    # New fields for review workflow
    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='new',
        help_text="Current review status of this broken link"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes from content managers about this link"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_broken_links'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['scan', 'target_url']]
        ordering = ['status_code', 'target_url']
        verbose_name = "Broken Link"
        verbose_name_plural = "Broken Links"

    def __str__(self):
        return f"{self.target_url} ({self.status_code})"

    @property
    def is_critical(self):
        """Returns True if this is a critical error (404, 400, 410, 0)"""
        return self.status_code in [0, 400, 404, 410]

    @property
    def severity(self):
        """Returns severity level for display"""
        if self.status_code in [0, 400, 404, 410]:
            return "CRITICAL"
        elif self.status_code in [401, 403, 429]:
            return "INVESTIGATE"
        else:
            return "ERROR"