# Quick Installation Guide

## Install from GitHub

### Add to requirements.txt (Recommended)

```
wagtail-linkaudit @ git+https://github.com/donaldushman/wagtail-linkaudit.git@v1.0.0
```

Then:
```bash
pip install -r requirements.txt
```

### Direct pip install

```bash
pip install git+https://github.com/donaldushman/wagtail-linkaudit.git@v1.0.0
```

### For private repositories

If you're using SSH keys:
```
wagtail-linkaudit @ git+ssh://git@github.com/donaldushman/wagtail-linkaudit.git@v3.0.2
```

## Version Pinning

**Always pin to a specific tag** (like `@v3.0.2`) for reproducible deployments. This ensures:
- ✅ Same code on all environments
- ✅ Easy rollback if needed
- ✅ No surprise changes from new commits

### Upgrading

When a new version is released:

1. Update your requirements.txt:
   ```
   wagtail-linkaudit @ git+https://github.com/donaldushman/wagtail-linkaudit.git@v3.0.0
   ```

2. Upgrade:
   ```bash
   pip install --upgrade -r requirements.txt
   ```

### Using commit SHA (maximum reproducibility)

For absolute certainty, pin to a specific commit:
```
wagtail-linkaudit @ git+https://github.com/donaldushman/wagtail-linkaudit.git@34fde95abc...
```

## Django Setup

After installation, add to `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'wagtail_linkaudit',
]

# Required settings
LINKAUDIT_EMAIL_RECIPIENTS = ['admin@example.com']
WAGTAIL_SITE_NAME = 'My Website'
BASE_URL = 'https://mywebsite.com'
```

Then run migrations:
```bash
python manage.py migrate wagtail_linkaudit
```

See [README.md](README.md) for full documentation.
