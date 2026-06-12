# Wagtail Link Audit

A Django/Wagtail app for scanning websites for broken links with an integrated admin workflow for content managers.

## Features

### Link Scanning
- Crawls website pages following internal links
- Checks external links for broken status
- Configurable depth and page limits
- **Simple synchronous scanning** - no task queue required!

### Admin Dashboard
- **Enhanced Scan List**: View scans with critical issue counts and review status
- **Broken Link Management**: Color-coded display with severity badges (Critical/Investigate)
- **Whitelist Management**: Add specific URLs or entire domains to exclusion list
- **Review Workflow**: Track link status (New, Under Review, Fixed, Whitelisted)

### Content Manager Workflow
1. Receive email notification when scan completes
2. Click admin link to view detailed results
3. Review broken links categorized by severity:
   - **CRITICAL** (red): 404, 400, 410, connection failures - requires immediate action
   - **INVESTIGATE** (yellow): 403, 401, 429, 5xx - may be false positives
4. Use admin actions:
   - Mark links as "Under Review" or "Fixed"
   - Whitelist specific URLs to prevent them from appearing in future scans
   - Export to CSV for external tracking
5. Add notes for team communication
6. Superusers can whitelist entire domains via Django admin when needed

### Email Notifications
- Simple summary email with critical counts
- Direct link to admin for full details
- No more large attachments or wrapped URLs

## Installation

### Install from GitHub

Add to your `requirements.txt`:
```
wagtail-linkaudit @ git+https://github.com/donaldushman/wagtail-linkaudit.git@v3.0.2
```

Or install directly:
```bash
pip install git+https://github.com/donaldushman/wagtail-linkaudit.git@v3.0.2
```

**Recommended:** Pin to a specific version tag (like `@v3.0.2`) for reproducible deployments.

### Setup

1. Add to your Django project:
```python
INSTALLED_APPS = [
    # ...
    'wagtail_modeladmin',  # Required for Wagtail 6.0+
    'wagtail_linkaudit',
]
```

2. Configure settings:
```python
# Email recipients for scan notifications
LINKAUDIT_EMAIL_RECIPIENTS = ['admin@example.com', 'content@example.com']

# Site information (or use Wagtail's Site model)
WAGTAIL_SITE_NAME = 'My Website'
BASE_URL = 'https://mywebsite.com'

# Admin URL (if customized)
WAGTAIL_ADMIN_URL = '/admin/'  # Default

# Email from address
WAGTAILADMIN_NOTIFICATION_FROM_EMAIL = 'noreply@example.com'
```

3. Run migrations:
```bash
python manage.py migrate
```

**That's it!** No Celery, Redis, RabbitMQ, or django-q2 required.

## Usage

### Running a Scan

Run a scan from the command line:

```bash
python manage.py run_link_scan
```

This will use the `BASE_URL` from your settings. You can customize the scan:

```bash
python manage.py run_link_scan --max-pages 1000 --max-depth 5
python manage.py run_link_scan --url https://example.com
```

**Options:**
- `--url`: Starting URL (defaults to BASE_URL from settings)
- `--max-pages`: Maximum number of pages to scan (default: 500)
- `--max-depth`: Maximum crawl depth (default: 3)

The scan runs synchronously and will print progress as it goes. When complete, an email notification is sent to the configured recipients.

### Scheduling Recurring Scans

You can schedule scans to run automatically using your preferred method:

#### Option 1: Cron (Linux/Mac)

Add to your crontab (`crontab -e`):

```cron
# Run link scan every Sunday at 2 AM
0 2 * * 0 cd /path/to/project && /path/to/venv/bin/python manage.py run_link_scan

# Or weekly with custom settings
0 2 * * 0 cd /path/to/project && /path/to/venv/bin/python manage.py run_link_scan --max-pages 1000
```

#### Option 2: Systemd Timer (Linux)

Create `/etc/systemd/system/linkaudit-scan.service`:
```ini
[Unit]
Description=Run Link Audit Scan

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python manage.py run_link_scan
```

Create `/etc/systemd/system/linkaudit-scan.timer`:
```ini
[Unit]
Description=Weekly Link Audit Scan

[Timer]
OnCalendar=Sun 02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable --now linkaudit-scan.timer
```

#### Option 3: Heroku Scheduler

Add to Heroku Scheduler (free add-on):
```bash
python manage.py run_link_scan
```

Schedule: Daily, Weekly, or Monthly

**No worker dyno required!** The scan runs as a one-off process.

#### Option 4: Task Scheduler (Windows)

Create a scheduled task that runs:
```cmd
C:\path\to\venv\Scripts\python.exe C:\path\to\project\manage.py run_link_scan
```

### Cleanup Old Scans

Remove old scan data:

```bash
python manage.py cleanup_old_scans --days 90
```

Schedule this monthly to keep your database clean.

### Managing Broken Links

1. **View Results**: Go to Wagtail Admin → Settings → Link Audit → Broken Links
2. **Filter by Status**: Use filters to see New, Reviewing, Fixed, etc.
3. **Filter by Scan**: Select a specific scan to view its results
4. **Search**: Search by URL or notes
5. **Take Action on Individual Links**:
   - Click on a broken link to view details
   - Use action buttons: "Mark Reviewing", "Mark Fixed", "False Positive", "Whitelist Domain"
   - Add notes explaining the issue or resolution
6. **Quick Actions**: 
   - "Whitelist Domain" extracts the domain and adds it to whitelist automatically
   - "View Broken Links" button on each scan shows only that scan's results

### Whitelist Management

Go to Wagtail Admin → Settings → Link Audit → Whitelisted Domains

Pre-populate common bot-blocking domains:
- linkedin.com
- facebook.com
- twitter.com / x.com
- instagram.com

Or use the admin action to whitelist domains directly from broken links.

## Models

### Scan
Represents a single link audit scan with metadata and statistics.

### BrokenLink
Individual broken link with:
- Source and target URLs
- Status code
- Review status (new, reviewing, whitelisted, fixed)
- Notes field for team communication
- Reviewed by/at tracking

### WhitelistedURL
Specific URLs excluded from broken link reporting. Available in Wagtail admin for content managers.
- Two match types: `exact` (URL only) or `prefix` (URL and all paths under it)
- Provides granular control over what to exclude

### WhitelistedDomain
Entire domains excluded from broken link reporting (e.g., LinkedIn, which blocks bots). 
- Only accessible via Django admin (superuser access required)
- Use when you need to whitelist all URLs from a domain

### URL
Internal tracking of all URLs checked during scan.

## Admin Actions

**Scan Admin:**
- Stop running scans
- Delete old scans (30/90 days)

**Broken Link Admin:**
- Mark as "Under Review"
- Mark as "Fixed"
- Whitelist specific URLs (content managers via Wagtail admin)
- Export to CSV

**Whitelist Management:**
- WhitelistedURL - Wagtail admin (Settings → Link Audit)
- WhitelistedDomain - Django admin only (superusers)

## Management Commands

### Stop Running Scans
```bash
python manage.py stop_running_scans
python manage.py stop_running_scans --mark-as=failed
```

## Task Reference

- `crawl_page(scan_id, url, depth)` - Crawl internal page and follow links
- `check_link(scan_id, source_url, target_url)` - Check external link status
- `check_scan_completion(scan_id, previous_count)` - Monitor and complete scans
- `send_scan_results_email(scan_id)` - Send notification email
- `cleanup_old_scans(days_to_keep=90)` - Scheduled cleanup task

## Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `LINKAUDIT_EMAIL_RECIPIENTS` | `[]` | List of email addresses for notifications |
| `WAGTAIL_SITE_NAME` | Required | Site name for email subject |
| `BASE_URL` | Required | Base URL for scanning |
| `WAGTAIL_ADMIN_URL` | `/admin/` | Custom admin URL path |
| `WAGTAILADMIN_NOTIFICATION_FROM_EMAIL` | Required | From address for emails |

## Why No Task Queue?

This app uses a simple synchronous approach instead of Celery or django-q2:
- ✅ **Zero infrastructure** - no Redis, RabbitMQ, or worker processes
- ✅ **Simple deployment** - works on any hosting (Heroku, PythonAnywhere, shared hosting)
- ✅ **Easy scheduling** - use cron, systemd timers, or Heroku Scheduler
- ✅ **No extra costs** - no worker dynos or additional services
- ✅ **Easier debugging** - straightforward synchronous execution

Perfect for small-to-medium sites. For very large sites (1000+ pages), consider running scans less frequently or increasing the timeout.

## Differences from Multi-Site Version

This standalone version is designed for deployment to individual sites:
- ✅ No Site model - uses current Wagtail site
- ✅ Simplified configuration via Django settings
- ✅ Single-site focus with better admin UX
- ✅ Integrated review workflow for content managers
- ✅ Whitelist management in admin
- ✅ Simplified email notifications
- ✅ No task queue required (v3.0+)
