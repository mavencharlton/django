import csv
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Load fuel station data from CSV into the database"

    def handle(self, *args, **kwargs):
        from apps.fuel_stations.models import FuelStation

        path = settings.FUEL_DATA_CSV
        best = {}

        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    price = float(row["Retail Price"])
                except (ValueError, KeyError):
                    continue
                key = (row["Truckstop Name"].strip(), row["City"].strip(), row["State"].strip())
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

        FuelStation.objects.all().delete()
        FuelStation.objects.bulk_create([
            FuelStation(
                opis_id      = s["opis_id"],
                name         = s["name"],
                address      = s["address"],
                city         = s["city"],
                state        = s["state"],
                rack_id      = s["rack_id"],
                retail_price = s["price"],
            )
            for s in best.values()
        ])

        total    = FuelStation.objects.count()
        states   = FuelStation.objects.values("state").distinct().count()
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {total} stations across {states} states."
        ))
