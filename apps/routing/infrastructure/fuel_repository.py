from apps.fuel_stations.models import FuelStation


# Thin wrapper around the FuelStation ORM query.
# The service layer never touches Django models directly —
# it only calls this function and gets back a plain dict.


def cheapest_in_state(state: str) -> dict | None:
    """Return the cheapest fuel station in a given state.

    Stations are pre-sorted by retail_price in the model's Meta,
    so .first() always gives the cheapest one.
    Returns None if no stations are found for that state.
    """
    station = (
        FuelStation.objects
        .filter(state=state)
        .order_by("retail_price")
        .first()
    )
    if not station:
        return None
    return {
        "name":  station.name,
        "city":  station.city,
        "price": station.retail_price,
    }
