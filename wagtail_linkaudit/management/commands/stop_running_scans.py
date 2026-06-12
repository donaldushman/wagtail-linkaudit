from django.core.management.base import BaseCommand
from django.utils import timezone
from wagtail_linkaudit.models import Scan


class Command(BaseCommand):
    help = 'Stop all running linkchecker scans'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mark-as',
            type=str,
            default='completed',
            choices=['completed', 'failed'],
            help='Mark scans as completed or failed (default: completed)',
        )

    def handle(self, *args, **options):
        mark_as = options['mark_as']
        
        running_scans = Scan.objects.filter(status='running')
        count = running_scans.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No running scans found.'))
            return
        
        for scan in running_scans:
            duration = (timezone.now() - scan.started_at).total_seconds() / 3600
            self.stdout.write(
                f'Stopping Scan #{scan.id} - '
                f'Running for {duration:.1f} hours, {scan.pages_scanned} pages scanned'
            )
        
        running_scans.update(
            status=mark_as,
            finished_at=timezone.now()
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully stopped {count} scan(s) and marked as {mark_as}.')
        )
