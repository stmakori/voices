import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from Voices.models import Resource


class Command(BaseCommand):
    help = "Import hospitals from Overpass API JSON data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="hospital_data.json",
            help="Path to Overpass hospital JSON file (default: hospital_data.json)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of hospitals to import (default: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview import without saving to database",
        )

    def handle(self, *args, **options):
        with open(options["file"], "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_elements = data.get("elements", [])
        elements = []
        for e in raw_elements:
            tags = e.get("tags", {})
            if tags.get("amenity") != "hospital":
                continue
            if not tags.get("name"):
                continue
            elements.append(e)

        self.stdout.write(self.style.SUCCESS(f"Found {len(elements)} amenity=hospital entries"))

        def coords_for(elem):
            if elem.get("type") == "node":
                return elem.get("lat"), elem.get("lon")
            center = elem.get("center", {})
            return center.get("lat"), center.get("lon")

        def score(elem):
            tags = elem.get("tags", {})
            name = tags.get("name", "").strip().lower()
            s = 0

            if elem.get("type") == "way":
                s += 80
            elif elem.get("type") == "relation":
                s += 70
            else:
                s += 40

            if tags.get("building"):
                s += 20
            if tags.get("healthcare") in {"hospital", "counselling"}:
                s += 15
            if tags.get("opening_hours"):
                s += 8
            if tags.get("operator") or tags.get("operator:type") or tags.get("operator_type"):
                s += 8
            if tags.get("emergency") == "yes":
                s += 8
            if tags.get("addr:city"):
                s += 5
            if tags.get("addr:street"):
                s += 5

            # Prefer full facility names over ambiguous short names
            if len(name) >= 10:
                s += 6
            if "hospital" in name:
                s += 8
            if "dispensary" in name or "clinic" in name:
                s -= 8
            if name in {"grh", "naivasha"}:
                s -= 20

            return s

        # Keep best candidate per (normalized-name + rounded-coords)
        ranked = sorted(elements, key=score, reverse=True)
        deduped = []
        seen = set()
        for elem in ranked:
            tags = elem.get("tags", {})
            lat, lon = coords_for(elem)
            if lat is None or lon is None:
                continue
            key = (tags.get("name", "").strip().lower(), round(float(lat), 6), round(float(lon), 6))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(elem)

        limit = options["limit"]
        selected = deduped[:limit]
        self.stdout.write(self.style.SUCCESS(f"Selected {len(selected)} hospitals (requested limit: {limit})"))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for elem in selected:
            tags = elem.get("tags", {})
            lat, lon = coords_for(elem)
            if lat is None or lon is None:
                skipped_count += 1
                continue

            name = tags.get("name", "Unknown Hospital").strip()
            location = tags.get("addr:city") or "Nakuru County"
            address = tags.get("addr:street") or ""
            description = tags.get("description") or f"Imported from OpenStreetMap (osm:{elem.get('type')}/{elem.get('id')})."

            qs = Resource.objects.filter(
                name=name,
                resource_type="hospital",
                latitude=lat,
                longitude=lon,
            )
            resource = qs.first()

            if resource is None:
                if options["dry_run"]:
                    created_count += 1
                    continue
                Resource.objects.create(
                    name=name,
                    resource_type="hospital",
                    location=location,
                    address=address,
                    description=description,
                    latitude=lat,
                    longitude=lon,
                    is_verified=True,
                    verified_at=timezone.now(),
                    last_confirmed_at=timezone.now(),
                )
                created_count += 1
            else:
                changed = False
                if not resource.location:
                    resource.location = location
                    changed = True
                if not resource.address and address:
                    resource.address = address
                    changed = True
                if not resource.description and description:
                    resource.description = description
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
                    updated_count += 1
                else:
                    skipped_count += 1

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would create: {created_count}, update: {updated_count}, skip: {skipped_count}"
                )
            )
            return

        total_hospitals = Resource.objects.filter(resource_type="hospital").count()
        self.stdout.write(
            self.style.SUCCESS(
                "\nImport complete:\n"
                f"  Created: {created_count}\n"
                f"  Updated: {updated_count}\n"
                f"  Skipped: {skipped_count}\n"
                f"  Hospitals in database: {total_hospitals}"
            )
        )
