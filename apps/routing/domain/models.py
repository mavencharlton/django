from dataclasses import dataclass, field


@dataclass
class FuelStop:
    miles_into_route: float
    state: str
    station_name: str
    city: str
    price_per_gallon: float


@dataclass
class Route:
    start: str
    end: str
    total_miles: float
    total_cost: float
    fuel_stops: list[FuelStop]
    cost_breakdown: list[dict]
    geometry: dict = field(default_factory=dict)  # GeoJSON LineString
