"""
Management command: backfill_submitted_by
Matches historical GBVReport records (submitted_by=NULL) to Django users
by looking up the email the submitter provided when filing the report.

Usage:
    python manage.py backfill_submitted_by            # live run
    python manage.py backfill_submitted_by --dry-run  # preview only
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Voices.models import GBVReport


class Command(BaseCommand):
    help = "Backfill GBVReport.submitted_by using the report email field."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview matches without writing any changes to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("--- DRY RUN: no changes will be saved ---\n"))

        qs = (
            GBVReport.objects.filter(submitted_by__isnull=True)
            .exclude(email="")
            .exclude(email__isnull=True)
        )

        self.stdout.write(f"Reports without submitted_by and with an email: {qs.count()}")

        matched = 0
        skipped = 0

        for report in qs:
            try:
                user = User.objects.get(email=report.email)
            except User.DoesNotExist:
                skipped += 1
                self.stdout.write(
                    f"  Report #{report.id}: no user found for {report.email} — skipped."
                )
                continue
            except User.MultipleObjectsReturned:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  Report #{report.id}: multiple users share {report.email} — skipped."
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY RUN] Report #{report.id} ({report.email}) → user '{user.username}'"
                )
            else:
                report.submitted_by = user
                report.save(update_fields=["submitted_by"])
                self.stdout.write(
                    f"  Report #{report.id} ({report.email}) → '{user.username}' ✓"
                )
            matched += 1

        suffix = " (dry run — no changes saved)" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Matched: {matched}  Skipped (no unique match): {skipped}{suffix}"
            )
        )
