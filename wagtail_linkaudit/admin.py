from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from datetime import timedelta
from urllib.parse import urlparse
from .models import Scan, URL, BrokenLink, WhitelistedDomain, WhitelistedURL, EmailRecipient


@admin.register(WhitelistedDomain)
class WhitelistedDomainAdmin(admin.ModelAdmin):
    """Django admin for WhitelistedDomain - accessible only to superusers
    
    Content managers should use WhitelistedURL in the Wagtail admin instead.
    """
    list_display = ('domain', 'reason', 'added_by', 'added_at')
    search_fields = ('domain', 'reason')
    readonly_fields = ('added_by', 'added_at')
    ordering = ('domain',)

    def save_model(self, request, obj, form, change):
        if not change:  # Only set added_by on creation
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WhitelistedURL)
class WhitelistedURLAdmin(admin.ModelAdmin):
    """Django admin for WhitelistedURL - also available in Wagtail admin for content managers"""
    list_display = ('url', 'match_type', 'reason', 'added_by', 'added_at')
    list_filter = ('match_type', 'added_at')
    search_fields = ('url', 'reason')
    readonly_fields = ('added_by', 'added_at')
    ordering = ('url',)

    def save_model(self, request, obj, form, change):
        if not change:  # Only set added_by on creation
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailRecipient)
class EmailRecipientAdmin(admin.ModelAdmin):
    """Django admin for EmailRecipient - also available in Wagtail admin"""
    list_display = ('email', 'name', 'is_active', 'added_by', 'added_at')
    list_filter = ('is_active', 'added_at')
    search_fields = ('email', 'name')
    readonly_fields = ('added_by', 'added_at')
    ordering = ('email',)

    def save_model(self, request, obj, form, change):
        if not change:  # Only set added_by on creation
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'started_at', 
        'finished_at', 
        'status', 
        'pages_scanned',
        'total_urls',
        'critical_issues',
        'needs_review',
        'view_broken_links'
    )
    list_filter = ('status', 'started_at')
    ordering = ('-started_at',)
    list_per_page = 50
    date_hierarchy = 'started_at'
    actions = ['stop_running_scans', 'delete_old_scans_30_days', 'delete_old_scans_90_days']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            _total_urls=Count('url', distinct=True),
            _critical_count=Count(
                'brokenlink',
                filter=Q(
                    brokenlink__status_code__in=[0, 400, 404, 410]
                ) & ~Q(brokenlink__review_status='whitelisted'),
                distinct=True
            ),
            _needs_review=Count(
                'brokenlink',
                filter=~Q(brokenlink__review_status__in=['whitelisted', 'fixed']),
                distinct=True
            )
        )
        return qs
    
    def total_urls(self, obj):
        return obj._total_urls
    total_urls.short_description = 'Total URLs'
    total_urls.admin_order_field = '_total_urls'
    
    def critical_issues(self, obj):
        count = obj._critical_count
        if count > 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', count)
        return count
    critical_issues.short_description = 'Critical'
    critical_issues.admin_order_field = '_critical_count'
    
    def needs_review(self, obj):
        count = obj._needs_review
        if count > 0:
            return format_html('<span style="color: orange; font-weight: bold;">{}</span>', count)
        return count
    needs_review.short_description = 'Needs Review'
    needs_review.admin_order_field = '_needs_review'
    
    def view_broken_links(self, obj):
        url = reverse('admin:wagtail_linkaudit_brokenlink_changelist') + f'?scan__id__exact={obj.id}'
        return format_html('<a href="{}">View Broken Links</a>', url)
    view_broken_links.short_description = 'Actions'
    
    @admin.action(description='Stop selected running scans')
    def stop_running_scans(self, request, queryset):
        running = queryset.filter(status='running')
        count = running.count()
        if count > 0:
            running.update(status='completed', finished_at=timezone.now())
            self.message_user(request, f"Stopped {count} running scan(s)")
        else:
            self.message_user(request, "No running scans in selection")
    
    @admin.action(description='Delete scans older than 30 days')
    def delete_old_scans_30_days(self, request, queryset):
        cutoff = timezone.now() - timedelta(days=30)
        count = Scan.objects.filter(started_at__lt=cutoff).delete()[0]
        self.message_user(request, f"Deleted {count} scan(s) older than 30 days")
    
    @admin.action(description='Delete scans older than 90 days')
    def delete_old_scans_90_days(self, request, queryset):
        cutoff = timezone.now() - timedelta(days=90)
        count = Scan.objects.filter(started_at__lt=cutoff).delete()[0]
        self.message_user(request, f"Deleted {count} scan(s) older than 90 days")


@admin.register(URL)
class URLAdmin(admin.ModelAdmin):
    list_display = ('url', 'scan', 'status_code', 'is_broken')
    list_filter = ('is_broken', 'status_code', 'scan')
    search_fields = ('url',)
    list_per_page = 100


class SeverityFilter(admin.SimpleListFilter):
    title = 'severity'
    parameter_name = 'severity'

    def lookups(self, request, model_admin):
        return (
            ('critical', 'Critical (404, 400, 410, 0)'),
            ('investigate', 'Investigate (403, 401, 429)'),
            ('other', 'Other Errors'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'critical':
            return queryset.filter(status_code__in=[0, 400, 404, 410])
        elif self.value() == 'investigate':
            return queryset.filter(status_code__in=[401, 403, 429])
        elif self.value() == 'other':
            return queryset.exclude(status_code__in=[0, 400, 401, 403, 404, 410, 429])


@admin.register(BrokenLink)
class BrokenLinkAdmin(admin.ModelAdmin):
    list_display = (
        'colored_target_url',
        'severity_badge', 
        'status_code',
        'review_status',
        'source_url_link',
        'scan',
        'reviewed_info'
    )
    list_filter = (
        SeverityFilter,
        'review_status',
        'status_code',
        'scan',
    )
    search_fields = ('source_url', 'target_url', 'notes')
    list_per_page = 100
    readonly_fields = ('scan', 'source_url', 'target_url', 'status_code', 'reviewed_by', 'reviewed_at')
    fields = (
        'scan',
        'target_url',
        'source_url', 
        'status_code',
        'review_status',
        'notes',
        'reviewed_by',
        'reviewed_at',
    )
    actions = [
        'mark_as_reviewing',
        'mark_as_fixed',
        'mark_as_false_positive',
        'whitelist_domains',
        'export_to_csv',
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('scan', 'reviewed_by')

    def colored_target_url(self, obj):
        """Display target URL with color coding based on severity"""
        color = 'red' if obj.is_critical else 'orange'
        max_length = 80
        url_display = obj.target_url if len(obj.target_url) <= max_length else obj.target_url[:max_length] + '...'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            url_display
        )
    colored_target_url.short_description = 'Target URL'
    colored_target_url.admin_order_field = 'target_url'

    def severity_badge(self, obj):
        """Display severity badge"""
        severity = obj.severity
        colors = {
            'CRITICAL': '#dc3545',
            'INVESTIGATE': '#ffc107',
            'ERROR': '#6c757d'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(severity, '#6c757d'),
            severity
        )
    severity_badge.short_description = 'Severity'

    def source_url_link(self, obj):
        """Display source URL as clickable link"""
        max_length = 60
        url_display = obj.source_url if len(obj.source_url) <= max_length else obj.source_url[:max_length] + '...'
        return format_html('<a href="{}" target="_blank">{}</a>', obj.source_url, url_display)
    source_url_link.short_description = 'Found On'

    def reviewed_info(self, obj):
        """Display who reviewed and when"""
        if obj.reviewed_by and obj.reviewed_at:
            return format_html(
                '<small>{}<br/>{}</small>',
                obj.reviewed_by.get_full_name() or obj.reviewed_by.username,
                obj.reviewed_at.strftime('%Y-%m-%d %H:%M')
            )
        return '-'
    reviewed_info.short_description = 'Reviewed'

    @admin.action(description='Mark as "Under Review"')
    def mark_as_reviewing(self, request, queryset):
        count = queryset.update(
            review_status='reviewing',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f"Marked {count} link(s) as under review")

    @admin.action(description='Mark as "Fixed"')
    def mark_as_fixed(self, request, queryset):
        count = queryset.update(
            review_status='fixed',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f"Marked {count} link(s) as fixed")

    @admin.action(description='Mark as "False Positive"')
    def mark_as_false_positive(self, request, queryset):
        count = queryset.update(
            review_status='false_positive',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f"Marked {count} link(s) as false positive")

    @admin.action(description='Add domains to whitelist')
    def whitelist_domains(self, request, queryset):
        """Extract domains from selected broken links and add to whitelist"""
        domains = set()
        for link in queryset:
            domain = urlparse(link.target_url).netloc.lower()
            if domain:
                domains.add(domain)
        
        created_count = 0
        existing_count = 0
        
        for domain in domains:
            obj, created = WhitelistedDomain.objects.get_or_create(
                domain=domain,
                defaults={
                    'reason': 'Added from broken link scan - likely bot blocking',
                    'added_by': request.user,
                }
            )
            if created:
                created_count += 1
            else:
                existing_count += 1
        
        # Mark the selected links as whitelisted
        queryset.update(
            review_status='whitelisted',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        
        message = f"Added {created_count} domain(s) to whitelist"
        if existing_count > 0:
            message += f" ({existing_count} already existed)"
        message += f". Marked {queryset.count()} link(s) as whitelisted."
        self.message_user(request, message)

    @admin.action(description='Export to CSV')
    def export_to_csv(self, request, queryset):
        """Export selected broken links to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="broken_links.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Target URL', 
            'Status Code', 
            'Severity',
            'Source URL', 
            'Review Status',
            'Notes',
            'Scan ID',
            'Reviewed By',
            'Reviewed At'
        ])
        
        for link in queryset:
            writer.writerow([
                link.target_url,
                link.status_code,
                link.severity,
                link.source_url,
                link.get_review_status_display(),
                link.notes,
                link.scan_id,
                link.reviewed_by.username if link.reviewed_by else '',
                link.reviewed_at.strftime('%Y-%m-%d %H:%M') if link.reviewed_at else ''
            ])
        
        return response

    def save_model(self, request, obj, form, change):
        """Auto-set reviewed_by and reviewed_at when review_status changes"""
        if change and 'review_status' in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
