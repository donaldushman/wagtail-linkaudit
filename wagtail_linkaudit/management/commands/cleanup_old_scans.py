from django.core.management.base import BaseCommand
from wagtail_linkaudit.scanner import cleanup_old_scans


class Command(BaseCommand):
    help = 'Delete old link audit scans'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete scans older than this many days (default: 90)',
        )

    def handle(self, *args, **options):
        days = options['days']
        
        self.stdout.write(f'Cleaning up scans older than {days} days...\n')
        
        count = cleanup_old_scans(days_to_keep=days)
        
        if count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'✓ Deleted {count} old scan(s)'
            ))
        else:
            self.stdout.write('No old scans to delete')
