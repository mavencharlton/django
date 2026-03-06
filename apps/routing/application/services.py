import math
from django.conf import settings

from apps.routing.application.commands import PlanRouteCommand
from apps.routing.domain.models import Route, FuelStop
from apps.routing.infrastructure.ors_client import geocode, get_route
from apps.routing.infrastructure.fuel_repository import cheapest_in_state
from apps.routing.infrastructure.state_lookup import get_state_from_coords


# Vehicle constants come from settings so they're easy to change without
# touching business logic.
METERS_PER_MILE = 1609.34
MAX_RANGE = settings.VEHICLE_MAX_RANGE  # 500 miles
MPG = settings.VEHICLE_MPG        # 10


def haversine(a, b):
    """Straight-line distance in miles between two [lon, lat] points.

    Used to walk the route geometry and accumulate distance between
    waypoints — tells us when the vehicle needs to stop for fuel.
    """
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


class RouteService:
    """Orchestrates everything needed to plan a fuel-optimised route.

    Flow:
        1. Geocode start and end locations (ORS calls 1 & 2)
        2. Fetch the driving route (ORS call 3 — final call)
        3. Walk the route geometry, drop a fuel stop every MAX_RANGE miles
        4. Use offline state lookup to identify which state each stop is in
        5. Query the DB for the cheapest station in that state
        6. Calculate total fuel cost leg by leg
        7. Return a Route domain object
    """

    def plan(self, cmd: PlanRouteCommand) -> Route:
        # Geocode — converts city names to coordinates
        start_coords, start_label = geocode(cmd.start)
        end_coords,   end_label = geocode(cmd.end)

        # Single route call — returns GeoJSON with geometry + distance
        route_data = get_route(start_coords, end_coords)
        feature = route_data["features"][0]
        total_meters = feature["properties"]["summary"]["distance"]
        total_miles = total_meters / METERS_PER_MILE
        waypoints = feature["geometry"]["coordinates"]  # list of [lon, lat]

        # Build a list of (distance, coord) pairs between each waypoint
        segments = [
            (haversine(waypoints[i-1], waypoints[i]), waypoints[i])
            for i in range(1, len(waypoints))
        ]

        # Walk the route, trigger a stop every MAX_RANGE miles.
        # Skip placing a stop if we're within 50 miles of the destination.
        stop_coords = []
        covered = total_dist = 0.0
        for dist, coord in segments:
            covered += dist
            total_dist += dist
            if covered >= MAX_RANGE and total_dist < total_miles - 50:
                stop_coords.append((total_dist, coord))
                covered = 0.0

        # Resolve each stop to a state and find the cheapest station — no API calls
        fuel_stops = []
        for miles_at, coord in stop_coords:
            state = get_state_from_coords(coord[0], coord[1])
            station = cheapest_in_state(state)
            if station:
                fuel_stops.append(FuelStop(
                    miles_into_route=round(miles_at, 1),
                    state=state,
                    station_name=station["name"],
                    city=station["city"],
                    price_per_gallon=round(station["price"], 3),
                ))

        # Identify start and end states for cost calculation
        start_state = get_state_from_coords(waypoints[0][0],  waypoints[0][1])
        end_state = get_state_from_coords(waypoints[-1][0], waypoints[-1][1])

        total_cost, breakdown = self._calculate_cost(
            total_miles, fuel_stops, start_state, end_state
        )

        return Route(
            start=start_label,
            end=end_label,
            total_miles=round(total_miles, 1),
            total_cost=total_cost,
            fuel_stops=fuel_stops,
            cost_breakdown=breakdown,
            geometry=feature["geometry"],
        )

    def _calculate_cost(self, total_miles, stops, start_state, end_state):
        """Calculate total fuel cost leg by leg.

        Each fill-up covers MAX_RANGE miles at 10 MPG = 50 gallons.
        Legs:
            - Start: fill up before driving, using cheapest station at origin state
            - En-route: fill up at each stop
            - Final: remaining miles after the last stop, priced at destination state
        """
        gallons_per_leg = MAX_RANGE / MPG  # 50 gallons
        total_cost = 0.0
        breakdown = []

        # Initial fill-up at departure
        start_station = cheapest_in_state(start_state)
        if start_station:
            cost = gallons_per_leg * start_station["price"]
            total_cost += cost
            breakdown.append({
                "at":               f"{start_station['name']}, {start_station['city']}, {start_state} (start)",
                "gallons":          gallons_per_leg,
                "price_per_gallon": round(start_station["price"], 3),
                "cost":             round(cost, 2),
            })

        # En-route stops
        for stop in stops:
            cost = gallons_per_leg * stop.price_per_gallon
            total_cost += cost
            breakdown.append({
                "at":               f"{stop.station_name}, {stop.city}, {stop.state}",
                "gallons":          gallons_per_leg,
                "price_per_gallon": stop.price_per_gallon,
                "cost":             round(cost, 2),
            })

        # Final leg — remaining distance after the last stop
        if stops:
            remaining = total_miles - stops[-1].miles_into_route
            end_station = cheapest_in_state(end_state)
            end_price = end_station["price"] if end_station else stops[-1].price_per_gallon
            last_gallons = remaining / MPG
            last_cost = last_gallons * end_price
            total_cost += last_cost
            breakdown.append({
                "at":               f"{end_station['name'] if end_station else 'Unknown'}, {end_state} (final leg)",
                "gallons":          round(last_gallons, 2),
                "price_per_gallon": round(end_price, 3),
                "cost":             round(last_cost, 2),
            })

        return round(total_cost, 2), breakdown
