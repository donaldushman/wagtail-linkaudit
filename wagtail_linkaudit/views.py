from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import BrokenLink, WhitelistedURL


@login_required
def mark_as_reviewing(request, pk):
    """Mark a broken link as under review"""
    link = get_object_or_404(BrokenLink, pk=pk)
    link.review_status = 'reviewing'
    link.reviewed_by = request.user
    link.reviewed_at = timezone.now()
    link.save()
    
    messages.success(request, f'Marked link as under review')
    return redirect('wagtail_linkaudit_brokenlink_modeladmin_index')


@login_required
def mark_as_fixed(request, pk):
    """Mark a broken link as fixed"""
    link = get_object_or_404(BrokenLink, pk=pk)
    link.review_status = 'fixed'
    link.reviewed_by = request.user
    link.reviewed_at = timezone.now()
    link.save()
    
    messages.success(request, f'Marked link as fixed')
    return redirect('wagtail_linkaudit_brokenlink_modeladmin_index')


@login_required
def whitelist_url(request, pk):
    """Add broken link URL to whitelist with exact match"""
    link = get_object_or_404(BrokenLink, pk=pk)
    target_url = link.target_url
    
    obj, created = WhitelistedURL.objects.get_or_create(
        url=target_url,
        defaults={
            'match_type': 'exact',
            'reason': 'Added from broken link review',
            'added_by': request.user,
        }
    )
    
    # Mark link as whitelisted
    link.review_status = 'whitelisted'
    link.reviewed_by = request.user
    link.reviewed_at = timezone.now()
    link.save()
    
    if created:
        messages.success(request, f'Added {target_url} to whitelist and marked link as whitelisted')
    else:
        messages.info(request, f'{target_url} was already whitelisted. Marked link as whitelisted.')
    
    return redirect('wagtail_linkaudit_brokenlink_modeladmin_index')
