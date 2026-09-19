import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from Voices.models import Resource


class Command(BaseCommand):
    help = 'Import churches from Overpass API JSON data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default='church_data.json',
            help='Path to Overpass church JSON file (default: church_data.json)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without saving',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Limit number of churches to import (default: 50)',
        )

    def handle(self, *args, **options):
        # Load church data from JSON file
        with open(options['file'], 'r', encoding='utf-8') as f:
            data = json.load(f)

        elements = data.get('elements', [])
        elements = [
            e for e in elements
            if e.get('tags', {}).get('amenity') == 'place_of_worship'
            and e.get('tags', {}).get('name')
            and e.get('tags', {}).get('religion', '').lower() == 'christian'
        ]
        
        # Separate ways (bigger) from nodes
        ways = [e for e in elements if e['type'] == 'way']
        nodes = [e for e in elements if e['type'] == 'node']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Found {len(ways)} ways (buildings) and {len(nodes)} nodes'
            )
        )
        
        # Score elements by size/quality
        def score_element(elem):
            """Score elements by likelihood of being substantial church"""
            score = 0
            
            # Ways (buildings) get higher priority
            if elem['type'] == 'way':
                score += 100
            
            # Check for address information
            tags = elem.get('tags', {})
            name = tags.get('name', '').lower()

            # Buildings and church structures are typically larger
            if tags.get('building'):
                score += 25

            # Prefer clearly established churches
            if any(word in name for word in ['cathedral', 'basilica', 'parish', 'chapel', 'st.', 'saint']):
                score += 15

            if tags.get('addr:city'):
                score += 30
            if tags.get('addr:street'):
                score += 20
            if tags.get('addr:postcode'):
                score += 15
            
            # Open/verified status
            if tags.get('operational_status') == 'open':
                score += 10
            
            # Multiple details
            if tags.get('denomination'):
                score += 5
            if tags.get('source'):
                score += 3
            
            return score
        
        # Combine and sort by quality
        all_elements = ways + nodes
        scored = [(elem, score_element(elem)) for elem in all_elements]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Drop exact duplicates by (name + rounded coordinates)
        deduped = []
        seen = set()
        for elem, score in scored:
            tags = elem.get('tags', {})
            name_key = tags.get('name', '').strip().lower()
            if elem['type'] == 'node':
                lat = elem.get('lat')
                lon = elem.get('lon')
            else:
                center = elem.get('center', {})
                lat = center.get('lat')
                lon = center.get('lon')
            if lat is None or lon is None:
                continue
            key = (name_key, round(float(lat), 6), round(float(lon), 6))
            if key in seen:
                continue
            seen.add(key)
            deduped.append((elem, score))
        
        # Take top N
        limit = options['limit']
        selected = [elem for elem, _ in deduped[:limit]]
        
        self.stdout.write(
            self.style.SUCCESS(f'Selected {len(selected)} churches to import')
        )
        
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for elem in selected:
            elem_type = elem['type']
            tags = elem.get('tags', {})
            name = tags.get('name', 'Unknown Church')
            
            # Get coordinates based on element type
            if elem_type == 'node':
                latitude = elem.get('lat')
                longitude = elem.get('lon')
            elif elem_type == 'way':
                center = elem.get('center', {})
                latitude = center.get('lat')
                longitude = center.get('lon')
            else:
                continue
            
            if not latitude or not longitude:
                skipped_count += 1
                continue
            
            # Extract location info
            location = tags.get('addr:city', '')
            if not location:
                # Try to infer from coordinates
                location = 'Nakuru County'
            
            address = tags.get('addr:street', '')
            osm_ref = f"osm:{elem_type}/{elem.get('id')}"
            description = f"Imported from OpenStreetMap ({osm_ref})."
            
            # Upsert by exact name+coordinates so same-name churches at different places are retained.
            try:
                resource = Resource.objects.filter(
                    name=name,
                    resource_type='church',
                    latitude=latitude,
                    longitude=longitude,
                ).first()

                if resource is None:
                    if options['dry_run']:
                        created_count += 1
                        self.stdout.write(
                            f'  ✓ [DRY RUN] Would create: {name} ({latitude:.4f}, {longitude:.4f})'
                        )
                        continue

                    Resource.objects.create(
                        name=name,
                        resource_type='church',
                        location=location,
                        address=address,
                        description=description,
                        latitude=latitude,
                        longitude=longitude,
                        is_verified=True,
                        verified_at=timezone.now(),
                        last_confirmed_at=timezone.now(),
                    )
                    created_count += 1
                    self.stdout.write(
                        f'  ✓ Created: {name} ({latitude:.4f}, {longitude:.4f})'
                    )
                else:
                    changed = False
                    if not resource.location:
                        resource.location = location
                        changed = True
                    if not resource.address and address:
                        resource.address = address
                        changed = True
                    if not resource.description:
                        resource.description = description
                        changed = True
                    if not resource.is_verified:
                        resource.is_verified = True
                        changed = True
                    if resource.last_confirmed_at is None:
                        resource.last_confirmed_at = timezone.now()
                        changed = True

                    if changed:
                        if not options['dry_run']:
                            resource.save()
                        updated_count += 1
                        self.stdout.write(
                            f'  ✓ Updated: {name}'
                        )
                    else:
                        skipped_count += 1
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error importing {name}: {str(e)}')
                )
                skipped_count += 1
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] No changes were made to the database.\n'
                    f'  Would create: {created_count}\n'
                    f'  Would update: {updated_count}\n'
                    f'  Would skip: {skipped_count}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Import complete:\n'
                    f'  Created: {created_count}\n'
                    f'  Updated: {updated_count}\n'
                    f'  Skipped: {skipped_count}\n'
                    f'  Total churches now in database: '
                    f'{Resource.objects.filter(resource_type="church").count()}'
                )
            )
