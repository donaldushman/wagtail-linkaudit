# Changelog

## Version 1.0.2 - Migration Fix (June 2026)

### Fixed
- **Critical**: Added missing `0001_initial.py` migration that was causing deployment failures
- The migration chain now properly starts with `0001_initial` instead of `0002`
- This fixes `NodeNotFoundError` when deploying to fresh databases

**Migration:**
```bash
python manage.py migrate wagtail_linkaudit
```

---

## Version 1.0.1 - Email Recipient Management (June 2026)

### New Feature: Manage Email Recipients via Admin

Added ability to manage scan notification recipients through the Wagtail admin interface.

**What's New:**
- **EmailRecipient Model**: Add/remove notification recipients via Wagtail admin
- **Active/Inactive Toggle**: Temporarily disable notifications without removing recipients
- **Combined Recipients**: Database recipients are combined with `LINKAUDIT_EMAIL_RECIPIENTS` setting
- **Admin Interface**: Located in Settings → Link Audit → Email Recipients

**Why This Change?**
- Content managers can add/remove team members without code changes
- Developers can still ensure critical emails (e.g., dev team) are always included via settings
- No duplicate emails sent - system automatically deduplicates
- Easier to manage growing teams or changing personnel

**Migration:**
```bash
python manage.py migrate wagtail_linkaudit
```

Existing `LINKAUDIT_EMAIL_RECIPIENTS` setting continues to work and is combined with database recipients.

---

## Version 1.0.0 - Initial Release (June 2026)

First public release of Wagtail Link Audit - a Django/Wagtail app for scanning websites for broken links with an integrated admin workflow. This is a single-site version of an existing application intended for consultants managing multiple client websites.

### Features

**Link Scanning:**
- Crawls website pages following internal links up to configurable depth
- Checks external links for broken status
- Configurable page limits and depth settings
- Simple synchronous scanning - no task queue required

**Wagtail Admin Integration:**
- Enhanced scan list with critical issue counts and review status
- Color-coded broken link display with severity badges (Critical/Investigate)
- Integrated review workflow for content managers
- Located in Settings → Link Audit menu

**Whitelist Management:**
- **WhitelistedURL**: Whitelist specific URLs with exact or prefix matching (Wagtail admin - content managers)
- **WhitelistedDomain**: Whitelist entire domains (Django admin - superusers only)
- Security-conscious access model for granular control

**Review Workflow:**
- Track link status: New, Under Review, Whitelisted, Fixed
- Add notes for team communication
- Track who reviewed and when
- One-click whitelist actions

**Email Notifications:**
- Summary email when scan completes
- Direct link to admin for detailed review
- Highlights critical issues requiring immediate attention

### Installation

Compatible with:
- Django 4.0+
- Wagtail 5.0+ and 6.0+
- Python 3.8+

### Deployment

No infrastructure dependencies required:
- No Redis or RabbitMQ needed
- No background worker processes
- No additional hosting costs
- Works on any hosting platform
- Schedule scans via cron or your preferred scheduler

### Usage

Run scans via management command:
```bash
python manage.py run_link_scan --url https://yoursite.com
```

Clean up old scans:
```bash
python manage.py cleanup_old_scans --days 90
```

### 🔧 Models

- **Scan**: Scan metadata and statistics
- **BrokenLink**: Individual broken links with review workflow
- **WhitelistedURL**: URL-specific whitelist entries
- **WhitelistedDomain**: Domain-wide whitelist entries
- **URL**: Internal tracking of all checked URLs

**Added:**
- New `scanner.py` module with synchronous scanning
- Management command: `python manage.py run_link_scan`
- Management command: `python manage.py cleanup_old_scans`
- Real-time progress output during scans
- Documentation for cron/systemd/Heroku Scheduler

#### Migration from v2.x

1. **Update package version:**
   ```
   wagtail-linkaudit @ git+https://github.com/donaldushman/wagtail-linkaudit.git@v3.0.0
   ```

2. **Remove from INSTALLED_APPS:**
   ```python
   INSTALLED_APPS = [
       # Remove 'django_q' if you were using it
       'wagtail_modeladmin',
       'wagtail_linkaudit',  # Keep this
   ]
   ```

3. **Remove from settings.py:**
   - Delete `Q_CLUSTER` configuration
   - Keep `LINKAUDIT_EMAIL_RECIPIENTS`, `BASE_URL`, etc.

4. **Stop worker processes:**
   ```bash
   # If using django-q2:
   # Stop qcluster process
   
   # If using Celery:
   # Stop celery worker and celery beat
   ```

5. **Update scheduled tasks:**
   - Remove cron jobs or scheduled tasks that called Celery/django-q2
   - Add new cron job: `python manage.py run_link_scan`
   - See README for cron/systemd examples

6. **Run migrations** (no database changes, but good practice):
   ```bash
   python manage.py migrate
   ```

#### New Usage

**Run a scan:**
```bash
python manage.py run_link_scan
python manage.py run_link_scan --max-pages 1000 --max-depth 5
```

**Schedule weekly scans (cron):**
```cron
0 2 * * 0 cd /path/to/project && /path/to/venv/bin/python manage.py run_link_scan
```

**Heroku Scheduler:**
```bash
python manage.py run_link_scan
```

No worker dyno needed!

---

## Version 2.1.0 - Wagtail Admin Integration (June 2026)

### New Features

#### Wagtail Admin Integration
- **Integrated with Wagtail Admin**: App now appears in Wagtail's sidebar under "Link Audit" (not Django admin)
- **ModelAdmin Group**: All models organized under a single "Link Audit" menu item
- **Custom Action Buttons**: Quick actions on individual broken links:
  - Mark as Reviewing
  - Mark as Fixed
  - Mark as False Positive
  - Whitelist Domain (one-click)
- **Enhanced Navigation**: "View Broken Links" button on each scan for quick access
- **Better Icons**: Custom Wagtail icons for each section (warning, tasks, tick-inverse, link)
- **Consistent UX**: Follows Wagtail's design patterns and styling

#### New Files
- `wagtail_hooks.py` - Registers ModelAdmin classes with Wagtail
- `views.py` - Custom action views for status updates and whitelisting

#### Technical Improvements
- Uses `wagtail.contrib.modeladmin` for admin interface
- Custom ButtonHelper classes for action buttons
- Maintains all existing functionality (color coding, severity badges, filters)
- Backward compatible with existing data

### Migration Notes
- **No database changes** - This is a UI-only upgrade
- Simply update to v2.1.0 and refresh your browser
- Old Django admin (`admin.py`) is still included but not registered by default

---

## Version 2.0 - Wagtail Link Audit (Single-Site Standalone)

### Major Changes from Multi-Site Version

#### Architecture
- **Removed Site Model**: No more multi-site management - app now works with the single site it's installed on
- **Simplified Configuration**: Uses Django settings instead of database-stored site information
- **Renamed App**: Changed from `linkchecker` to `wagtail_linkaudit` for clarity

#### Admin Enhancements

**New Models:**
- `WhitelistedDomain` - Manage domains that should be excluded from broken link reporting

**Enhanced BrokenLink Model:**
- Added `review_status` field (new, reviewing, whitelisted, fixed, false_positive)
- Added `notes` field for content manager comments
- Added `reviewed_by` and `reviewed_at` tracking
- Added `is_critical` and `severity` properties for categorization

**Scan Admin Improvements:**
- Display total URLs checked
- Show critical issue count (red highlight)
- Show needs review count (orange highlight)
- Direct link to view broken links for each scan
- Optimized queries with annotations

**BrokenLink Admin Improvements:**
- Color-coded URLs (red for critical, orange for investigate)
- Severity badges (CRITICAL, INVESTIGATE, ERROR)
- Custom severity filter
- Review status filter
- Enhanced search across URLs and notes
- Clickable source URLs
- Shows who reviewed and when

**New Admin Actions:**
- Mark as "Under Review"
- Mark as "Fixed"
- Mark as "False Positive"
- **Add domains to whitelist** (extracts domains and marks links as whitelisted)
- **Export to CSV** with all details

**WhitelistedDomain Admin:**
- Simple CRUD for managing whitelisted domains
- Auto-tracks who added domain and when

#### Email Notifications
- **Simplified**: No more large text attachments
- **Summary Only**: Shows critical count, investigate count, and basic stats
- **Direct Admin Link**: Click to view full details in admin
- **Smart Subject**: Indicates severity (Critical Issues vs. Needs Review vs. No Issues)

#### Whitelist System
- Database-driven whitelist
- Admin interface for managing whitelist
- One-click whitelist from broken links
- Whitelist checked before creating BrokenLink records
- Preserves hardcoded whitelist for common bot blockers

#### Workflow Improvements
1. Content manager receives email notification
2. Clicks link to admin
3. Sees broken links categorized by severity
4. Can filter, search, and bulk-update status
5. Can whitelist URLs directly
6. Can add notes for team communication
7. System tracks who reviewed what and when

### Technical Details

**Settings Required:**
- `LINKAUDIT_EMAIL_RECIPIENTS` - List of email addresses
- `WAGTAIL_SITE_NAME` - Site name
- `BASE_URL` - Base URL for links
- `WAGTAIL_ADMIN_URL` - Admin URL (optional, defaults to /admin/)

### Migration Path

From multi-site linkchecker to wagtail-linkaudit:

1. Fresh install (recommended):
   - Install as new app
   - Run makemigrations and migrate
   - Configure settings
   - Old scan data not migrated

2. Data migration (if needed):
   - Manual script to copy relevant scan data
   - Map site relationships to single site
   - Transform BrokenLink records to add new fields

### Future Enhancements (Ideas)

- Wagtail admin dashboard panel showing latest scan status
- Scheduled scans via Celery or Django tasks
- Re-check individual links from admin
- Link to specific page edit in Wagtail (for internal broken links)
- Historical trending of broken link counts
- Integration with Wagtail's workflow system

---

## Version 1.0 - Multi-Site Link Checker

Original multi-site version for consultant managing multiple client websites.
