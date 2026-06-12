# Generated manually for v1.0.1

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wagtail_linkaudit', '0002_whitelistedurl_and_remove_false_positive'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(help_text='Email address to receive scan notifications', max_length=254, unique=True)),
                ('name', models.CharField(blank=True, help_text='Name or description (optional)', max_length=255)),
                ('is_active', models.BooleanField(default=True, help_text='Uncheck to temporarily disable notifications')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('added_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='email_recipients',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Email Recipient',
                'verbose_name_plural': 'Email Recipients',
                'ordering': ['email'],
            },
        ),
    ]
