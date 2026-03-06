from apps.fuel_stations.models import FuelStation


def cheapest_in_state(state: str) -> dict | None:
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
