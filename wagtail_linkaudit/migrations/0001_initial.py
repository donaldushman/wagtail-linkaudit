# Generated for initial models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Scan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(null=True)),
                ('status', models.CharField(
                    choices=[
                        ('running', 'Running'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                    ],
                    default='running',
                    max_length=20
                )),
                ('max_pages', models.IntegerField(default=500)),
                ('max_depth', models.IntegerField(default=3)),
                ('pages_scanned', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='WhitelistedDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(help_text='Domain without protocol (e.g., linkedin.com)', max_length=255, unique=True)),
                ('reason', models.TextField(blank=True, help_text="Why this domain is whitelisted (e.g., 'Known to block bots')")),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('added_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='whitelisted_domains',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Whitelisted Domain',
                'verbose_name_plural': 'Whitelisted Domains',
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='URL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField()),
                ('status_code', models.IntegerField(null=True)),
                ('is_broken', models.BooleanField(default=False)),
                ('scan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wagtail_linkaudit.scan')),
            ],
            options={
                'verbose_name': 'URL',
                'verbose_name_plural': 'URLs',
            },
        ),
        migrations.CreateModel(
            name='BrokenLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_url', models.URLField()),
                ('target_url', models.URLField()),
                ('status_code', models.IntegerField()),
                ('review_status', models.CharField(
                    choices=[
                        ('new', 'New - Needs Review'),
                        ('reviewing', 'Under Review'),
                        ('false_positive', 'False Positive'),
                        ('fixed', 'Fixed'),
                    ],
                    default='new',
                    help_text='Current review status of this broken link',
                    max_length=20
                )),
                ('notes', models.TextField(blank=True, help_text='Notes from content managers about this link')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_broken_links',
                    to=settings.AUTH_USER_MODEL
                )),
                ('scan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wagtail_linkaudit.scan')),
            ],
            options={
                'verbose_name': 'Broken Link',
                'verbose_name_plural': 'Broken Links',
                'ordering': ['status_code', 'target_url'],
            },
        ),
        migrations.AddConstraint(
            model_name='url',
            constraint=models.UniqueConstraint(fields=('scan', 'url'), name='wagtail_linkaudit_url_scan_url_uniq'),
        ),
        migrations.AddConstraint(
            model_name='brokenlink',
            constraint=models.UniqueConstraint(fields=('scan', 'target_url'), name='wagtail_linkaudit_brokenlink_scan_target_url_uniq'),
        ),
    ]
