from wagtail_modeladmin.options import (
    ModelAdmin, ModelAdminGroup, modeladmin_register
)
from wagtail_modeladmin.helpers import ButtonHelper
from wagtail import hooks
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta

from .models import Scan, URL, BrokenLink, WhitelistedDomain, WhitelistedURL, EmailRecipient


class ScanButtonHelper(ButtonHelper):
    """Custom buttons for Scan admin"""
    
    def view_broken_links_button(self, obj):
        url = reverse('wagtail_linkaudit_brokenlink_modeladmin_index') + f'?scan__id__exact={obj.id}'
        return {
            'url': url,
            'label': 'View Broken Links',
            'classname': 'button button-small button-secondary',
            'title': 'View broken links for this scan',
        }
    
    def get_buttons_for_obj(self, obj, exclude=None, classnames_add=None, classnames_exclude=None):
        buttons = super().get_buttons_for_obj(obj, exclude, classnames_add, classnames_exclude)
        buttons.append(self.view_broken_links_button(obj))
        return buttons


class ScanAdmin(ModelAdmin):
    model = Scan
    menu_label = 'Scans'
    menu_icon = 'tasks'
    list_display = ('id', 'started_at', 'finished_at', 'status', 'pages_scanned', 'display_total_urls', 'display_critical', 'display_needs_review')
    list_filter = ('status', 'started_at')
    search_fields = ('id',)
    ordering = ('-started_at',)
    list_per_page = 50
    button_helper_class = ScanButtonHelper
    
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
    
    def display_total_urls(self, obj):
        return obj._total_urls
    display_total_urls.short_description = 'Total URLs'
    
    def display_critical(self, obj):
        count = obj._critical_count
        if count > 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', count)
        return count
    display_critical.short_description = 'Critical'
    
    def display_needs_review(self, obj):
        count = obj._needs_review
        if count > 0:
            return format_html('<span style="color: orange; font-weight: bold;">{}</span>', count)
        return count
    display_needs_review.short_description = 'Needs Review'


class BrokenLinkButtonHelper(ButtonHelper):
    """Custom buttons for BrokenLink admin"""
    
    def mark_reviewing_button(self, obj):
        return {
            'url': reverse('linkaudit_mark_reviewing', args=[obj.pk]),
            'label': 'Mark Reviewing',
            'classname': 'button button-small',
            'title': 'Mark as under review',
        }
    
    def mark_fixed_button(self, obj):
        return {
            'url': reverse('linkaudit_mark_fixed', args=[obj.pk]),
            'label': 'Mark Fixed',
            'classname': 'button button-small button-secondary',
            'title': 'Mark as fixed',
        }
    
    def whitelist_url_button(self, obj):
        return {
            'url': reverse('linkaudit_whitelist_url', args=[obj.pk]),
            'label': 'Whitelist This URL',
            'classname': 'button button-small button-warning',
            'title': 'Add this URL to whitelist (won\'t appear in future scans)',
        }
    
    def get_buttons_for_obj(self, obj, exclude=None, classnames_add=None, classnames_exclude=None):
        buttons = super().get_buttons_for_obj(obj, exclude, classnames_add, classnames_exclude)
        buttons.append(self.mark_reviewing_button(obj))
        buttons.append(self.mark_fixed_button(obj))
        buttons.append(self.whitelist_url_button(obj))
        return buttons


class BrokenLinkAdmin(ModelAdmin):
    model = BrokenLink
    menu_label = 'Broken Links'
    menu_icon = 'warning'
    list_display = ('display_target_url', 'display_severity', 'status_code', 'review_status', 'display_source_url', 'scan', 'display_reviewed')
    list_filter = ('review_status', 'status_code', 'scan')
    search_fields = ('target_url', 'source_url', 'notes')
    list_per_page = 100
    button_helper_class = BrokenLinkButtonHelper
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('scan', 'reviewed_by')
    
    def display_target_url(self, obj):
        """Display target URL with color coding based on severity"""
        color = 'red' if obj.is_critical else 'orange'
        max_length = 80
        url_display = obj.target_url if len(obj.target_url) <= max_length else obj.target_url[:max_length] + '...'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            url_display
        )
    display_target_url.short_description = 'Target URL'
    
    def display_severity(self, obj):
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
    display_severity.short_description = 'Severity'
    
    def display_source_url(self, obj):
        """Display source URL as clickable link"""
        max_length = 60
        url_display = obj.source_url if len(obj.source_url) <= max_length else obj.source_url[:max_length] + '...'
        return format_html('<a href="{}" target="_blank">{}</a>', obj.source_url, url_display)
    display_source_url.short_description = 'Found On'
    
    def display_reviewed(self, obj):
        """Display who reviewed and when"""
        if obj.reviewed_by and obj.reviewed_at:
            return format_html(
                '<small>{}<br/>{}</small>',
                obj.reviewed_by.get_full_name() or obj.reviewed_by.username,
                obj.reviewed_at.strftime('%Y-%m-%d %H:%M')
            )
        return '-'
    display_reviewed.short_description = 'Reviewed'


class WhitelistedURLAdmin(ModelAdmin):
    """Admin for whitelisted URLs - accessible to content managers via Wagtail admin"""
    model = WhitelistedURL
    menu_label = 'Whitelisted URLs'
    menu_icon = 'tick-inverse'
    list_display = ('url', 'match_type', 'reason', 'added_by', 'added_at')
    search_fields = ('url', 'reason')
    ordering = ('url',)
    list_filter = ('match_type', 'added_at')


class EmailRecipientAdmin(ModelAdmin):
    """Admin for email notification recipients"""
    model = EmailRecipient
    menu_label = 'Email Recipients'
    menu_icon = 'mail'
    list_display = ('email', 'name', 'is_active', 'added_by', 'added_at')
    list_filter = ('is_active', 'added_at')
    search_fields = ('email', 'name')
    ordering = ('email',)


class URLAdmin(ModelAdmin):
    model = URL
    menu_label = 'All URLs'
    menu_icon = 'link'
    list_display = ('url', 'scan', 'status_code', 'is_broken')
    list_filter = ('is_broken', 'status_code', 'scan')
    search_fields = ('url',)
    list_per_page = 100


class LinkAuditGroup(ModelAdminGroup):
    menu_label = 'Link Audit'
    menu_icon = 'link'
    menu_order = 300
    add_to_settings_menu = True
    items = (BrokenLinkAdmin, ScanAdmin, WhitelistedURLAdmin, EmailRecipientAdmin, URLAdmin)


modeladmin_register(LinkAuditGroup)


# Hook to add custom actions (mark as fixed, whitelist, etc.) via separate views
@hooks.register('register_admin_urls')
def register_linkaudit_urls():
    from django.urls import path
    from . import views
    
    return [
        path('linkaudit/brokenlink/<int:pk>/mark-reviewing/', views.mark_as_reviewing, name='linkaudit_mark_reviewing'),
        path('linkaudit/brokenlink/<int:pk>/mark-fixed/', views.mark_as_fixed, name='linkaudit_mark_fixed'),
        path('linkaudit/brokenlink/<int:pk>/whitelist-url/', views.whitelist_url, name='linkaudit_whitelist_url'),
    ]
