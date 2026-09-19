import json
from django.core.management.base import BaseCommand
from django.utils import timezone

from Voices.models import Resource


class Command(BaseCommand):
    help = "Import legal centers from JSON data"

    def add_arguments(self, parser):
        parser.add_argument("--file", default="legal_data.json", help="Path to JSON file")
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")

    def handle(self, *args, **options):
        with open(options["file"], "r", encoding="utf-8") as f:
            payload = json.load(f)

        entries = payload.get("legal_centers", [])
        created = 0
        updated = 0
        skipped = 0

        for entry in entries:
            name = (entry.get("name") or "").strip()
            lat = entry.get("latitude")
            lon = entry.get("longitude")
            location = (entry.get("location") or "Nakuru County").strip()
            address = (entry.get("address") or "Nakuru County").strip()
            phone = (entry.get("phone") or "").strip()

            if not name or lat is None or lon is None:
                skipped += 1
                continue

            resource = Resource.objects.filter(name=name, resource_type="legal").first()
            if resource is None:
                if options["dry_run"]:
                    created += 1
                    continue
                Resource.objects.create(
                    resource_type="legal",
                    name=name,
                    location=location,
                    address=address,
                    phone=phone,
                    description="Legal center / rights organization.",
                    latitude=float(lat),
                    longitude=float(lon),
                    is_verified=True,
                    verified_at=timezone.now(),
                    last_confirmed_at=timezone.now(),
                )
                created += 1
                continue

            changed = False
            if resource.latitude != float(lat) or resource.longitude != float(lon):
                resource.latitude = float(lat)
                resource.longitude = float(lon)
                changed = True
            if location and resource.location != location:
                resource.location = location
                changed = True
            if address and resource.address != address:
                resource.address = address
                changed = True
            if phone and resource.phone != phone:
                resource.phone = phone
                changed = True
            if not resource.is_verified:
                resource.is_verified = True
                changed = True
            if resource.last_confirmed_at is None:
                resource.last_confirmed_at = timezone.now()
                changed = True

            if changed:
                if not options["dry_run"]:
                    resource.save()
                updated += 1
            else:
                skipped += 1

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would create: {created}, update: {updated}, skip: {skipped}"))
            return

        total = Resource.objects.filter(resource_type="legal").count()
        self.stdout.write(self.style.SUCCESS(
            "Import complete:\n"
            f"  Created: {created}\n"
            f"  Updated: {updated}\n"
            f"  Skipped: {skipped}\n"
            f"  Legal centers in database: {total}"
        ))
