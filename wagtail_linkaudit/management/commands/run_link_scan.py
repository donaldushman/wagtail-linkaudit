from django.core.management.base import BaseCommand
from django.conf import settings
from wagtail_linkaudit.scanner import run_scan


class Command(BaseCommand):
    help = 'Run a link audit scan on your site'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='Starting URL (defaults to BASE_URL from settings)',
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=500,
            help='Maximum number of pages to scan (default: 500)',
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=3,
            help='Maximum crawl depth (default: 3)',
        )

    def handle(self, *args, **options):
        start_url = options['url'] or getattr(settings, 'BASE_URL', None)
        
        if not start_url:
            self.stdout.write(self.style.ERROR(
                'Error: No URL specified. Either pass --url or set BASE_URL in settings.py'
            ))
            return
        
        max_pages = options['max_pages']
        max_depth = options['max_depth']
        
        self.stdout.write(self.style.SUCCESS(
            f'\nStarting link audit scan...'
        ))
        self.stdout.write(f'URL: {start_url}')
        self.stdout.write(f'Max pages: {max_pages}')
        self.stdout.write(f'Max depth: {max_depth}\n')
        
        try:
            scan = run_scan(start_url, max_pages=max_pages, max_depth=max_depth)
            
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Scan #{scan.id} completed successfully!'
            ))
            self.stdout.write(f'Pages scanned: {scan.pages_scanned}')
            self.stdout.write(f'Critical issues: {scan.critical_broken_links_count}')
            self.stdout.write(f'Needs review: {scan.needs_review_count}')
            self.stdout.write(f'\nView results in Wagtail Admin → Link Audit → Broken Links')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'\n✗ Scan failed: {e}'
            ))
            raise
