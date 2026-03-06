from dataclasses import dataclass, field


@dataclass
class FuelStop:
    """A single fuel stop along the route.

    Represents the cheapest station found in a given state
    at the point where the vehicle needs to refuel.
    """
    miles_into_route: float   # how far into the trip this stop occurs
    state: str                # US state abbreviation e.g. "NE"
    station_name: str
    city: str
    price_per_gallon: float


@dataclass
class Route:
    """The complete result of a planned route.

    Holds everything needed to render the map and cost breakdown —
    built by RouteService and handed to the presentation layer.
    """
    start: str
    end: str
    total_miles: float
    total_cost: float
    fuel_stops: list[FuelStop]
    cost_breakdown: list[dict]
    # GeoJSON LineString for the map
    geometry: dict = field(default_factory=dict)
