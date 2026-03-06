import math
from django.conf import settings

from apps.routing.application.commands import PlanRouteCommand
from apps.routing.domain.models import Route, FuelStop
from apps.routing.infrastructure.ors_client import geocode, get_route
from apps.routing.infrastructure.fuel_repository import cheapest_in_state
from apps.routing.infrastructure.state_lookup import get_state_from_coords


METERS_PER_MILE = 1609.34
MAX_RANGE        = settings.VEHICLE_MAX_RANGE
MPG              = settings.VEHICLE_MPG


def haversine(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


class RouteService:

    def plan(self, cmd: PlanRouteCommand) -> Route:
        # ORS call 1 & 2 — geocode
        start_coords, start_label = geocode(cmd.start)
        end_coords,   end_label   = geocode(cmd.end)

        # ORS call 3 — route
        route_data   = get_route(start_coords, end_coords)
        feature      = route_data["features"][0]
        total_meters = feature["properties"]["summary"]["distance"]
        total_miles  = total_meters / METERS_PER_MILE
        waypoints    = feature["geometry"]["coordinates"]

        # Walk route, place stop every MAX_RANGE miles — offline, no API calls
        segments = [
            (haversine(waypoints[i-1], waypoints[i]), waypoints[i])
            for i in range(1, len(waypoints))
        ]

        stop_coords = []
        covered = total_dist = 0.0
        for dist, coord in segments:
            covered    += dist
            total_dist += dist
            if covered >= MAX_RANGE and total_dist < total_miles - 50:
                stop_coords.append((total_dist, coord))
                covered = 0.0

        # Offline state lookup — zero API calls
        fuel_stops = []
        for miles_at, coord in stop_coords:
            state   = get_state_from_coords(coord[0], coord[1])
            station = cheapest_in_state(state)
            if station:
                fuel_stops.append(FuelStop(
                    miles_into_route = round(miles_at, 1),
                    state            = state,
                    station_name     = station["name"],
                    city             = station["city"],
                    price_per_gallon = round(station["price"], 3),
                ))

        start_state = get_state_from_coords(waypoints[0][0],  waypoints[0][1])
        end_state   = get_state_from_coords(waypoints[-1][0], waypoints[-1][1])
        total_cost, breakdown = self._calculate_cost(
            total_miles, fuel_stops, start_state, end_state
        )

        return Route(
            start          = start_label,
            end            = end_label,
            total_miles    = round(total_miles, 1),
            total_cost     = total_cost,
            fuel_stops     = fuel_stops,
            cost_breakdown = breakdown,
            geometry       = feature["geometry"],
        )

    def _calculate_cost(self, total_miles, stops, start_state, end_state):
        gallons_per_leg = MAX_RANGE / MPG
        total_cost      = 0.0
        breakdown       = []

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

        for stop in stops:
            cost = gallons_per_leg * stop.price_per_gallon
            total_cost += cost
            breakdown.append({
                "at":               f"{stop.station_name}, {stop.city}, {stop.state}",
                "gallons":          gallons_per_leg,
                "price_per_gallon": stop.price_per_gallon,
                "cost":             round(cost, 2),
            })

        if stops:
            remaining   = total_miles - stops[-1].miles_into_route
            end_station = cheapest_in_state(end_state)
            end_price   = end_station["price"] if end_station else stops[-1].price_per_gallon
            last_gallons = remaining / MPG
            last_cost    = last_gallons * end_price
            total_cost  += last_cost
            breakdown.append({
                "at":               f"{end_station['name'] if end_station else 'Unknown'}, {end_state} (final leg)",
                "gallons":          round(last_gallons, 2),
                "price_per_gallon": round(end_price, 3),
                "cost":             round(last_cost, 2),
            })

        return round(total_cost, 2), breakdown
