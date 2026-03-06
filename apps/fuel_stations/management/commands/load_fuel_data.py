import csv
from django.core.management.base import BaseCommand
from django.conf import settings


# Run once after migrations: python manage.py load_fuel_data
# Clears the table and reloads from the CSV each time,
# so re-running it is safe and idempotent.


class Command(BaseCommand):
    """Loads fuel station data from the OPIS CSV into SQLite.

    Deduplicates by (name, city, state) — keeps the lowest price
    where a station appears multiple times. Uses bulk_create for speed.
    """
    help = "Load fuel station data from CSV into the database"

    def handle(self, *args, **kwargs):
        from apps.fuel_stations.models import FuelStation

        path = settings.FUEL_DATA_CSV
        best = {}  # (name, city, state) → cheapest row

        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    price = float(row["Retail Price"])
                except (ValueError, KeyError):
                    continue
                key = (row["Truckstop Name"].strip(),
                       row["City"].strip(), row["State"].strip())
                if key not in best or price < best[key]["price"]:
                    best[key] = {
                        "opis_id": int(row["OPIS Truckstop ID"]),
                        "name":    row["Truckstop Name"].strip(),
                        "address": row["Address"].strip(),
                        "city":    row["City"].strip(),
                        "state":   row["State"].strip(),
                        "rack_id": int(row["Rack ID"]),
                        "price":   price,
                    }

        # Wipe and reload — simpler than diffing
        FuelStation.objects.all().delete()
        FuelStation.objects.bulk_create([
            FuelStation(
                opis_id=s["opis_id"],
                name=s["name"],
                address=s["address"],
                city=s["city"],
                state=s["state"],
                rack_id=s["rack_id"],
                retail_price=s["price"],
            )
            for s in best.values()
        ])

        total = FuelStation.objects.count()
        states = FuelStation.objects.values("state").distinct().count()
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {total} stations across {states} states."
        ))
