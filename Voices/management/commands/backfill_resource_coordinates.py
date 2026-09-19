from django.core.management.base import BaseCommand

from Voices.models import Resource


class Command(BaseCommand):
    help = "Backfill missing Resource coordinates using Kenya-restricted geocoding."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview coordinate updates without saving to the database.",
        )
        parser.add_argument(
            "--default-county",
            default="Nakuru County",
            help="County fallback when a resource query has no county context.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-geocode all resources, not only those missing coordinates.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        default_county = options["default_county"]
        geocode_all = options["all"]

        queryset = Resource.objects.all().order_by("id")
        if not geocode_all:
            queryset = queryset.filter(latitude__isnull=True, longitude__isnull=True)

        total = queryset.count()
        self.stdout.write(f"Resources to process: {total}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--- DRY RUN: no changes will be written ---"))

        updated = 0
        skipped = 0

        for resource in queryset:
            old_lat, old_lon = resource.latitude, resource.longitude
            resource._geocode(default_county=default_county)

            if resource.latitude is None or resource.longitude is None:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"  Resource #{resource.id}: no coordinate match ({resource.name})")
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY RUN] Resource #{resource.id}: {resource.name} -> ({resource.latitude}, {resource.longitude})"
                )
            else:
                if old_lat != resource.latitude or old_lon != resource.longitude:
                    resource.save(update_fields=["latitude", "longitude"])
                    updated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Resource #{resource.id}: saved ({resource.latitude}, {resource.longitude})"
                        )
                    )
                else:
                    skipped += 1

        suffix = " (dry run)" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated: {updated}  Skipped: {skipped}  Total: {total}{suffix}"
            )
        )
