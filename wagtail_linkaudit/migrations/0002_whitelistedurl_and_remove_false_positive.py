# Generated manually for v3.1.0

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wagtail_linkaudit', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhitelistedURL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(help_text='Full URL to whitelist (e.g., https://example.com/page)', unique=True)),
                ('match_type', models.CharField(
                    choices=[('exact', 'Exact URL only'), ('prefix', 'URL and all paths under it')],
                    default='exact',
                    help_text='How to match this URL',
                    max_length=10
                )),
                ('reason', models.TextField(blank=True, help_text='Why this URL is whitelisted')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('added_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='whitelisted_urls',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Whitelisted URL',
                'verbose_name_plural': 'Whitelisted URLs',
                'ordering': ['url'],
            },
        ),
        migrations.AlterField(
            model_name='brokenlink',
            name='review_status',
            field=models.CharField(
                choices=[
                    ('new', 'New - Needs Review'),
                    ('reviewing', 'Under Review'),
                    ('whitelisted', 'Whitelisted'),
                    ('fixed', 'Fixed'),
                ],
                default='new',
                help_text='Current review status of this broken link',
                max_length=20
            ),
        ),
    ]
