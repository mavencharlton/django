from django.db import models


# Infrastructure concern — this model exists purely as a fast lookup table.
# The CSV is loaded once via load_fuel_data and queried by state on every request.
# It is NOT a domain object — the domain only ever sees plain dicts from
# fuel_repository.py, never this model directly.


class FuelStation(models.Model):
    """Stores fuel station data loaded from the OPIS CSV.

    Indexed by state so cheapest-in-state queries are fast.
    Duplicates in the CSV are resolved at load time — one record
    per unique (name, city, state) combination, keeping the lowest price.
    """
    opis_id = models.IntegerField()
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField()
    retail_price = models.FloatField()

    class Meta:
        ordering = ["retail_price"]

    def __str__(self):
        return f"{self.name} — {self.city}, {self.state} (${self.retail_price})"
