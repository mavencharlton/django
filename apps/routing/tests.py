from unittest.mock import patch, MagicMock
from django.test import TestCase

from apps.routing.application.commands import PlanRouteCommand
from apps.routing.application.services import RouteService
from apps.routing.domain.models import Route, FuelStop


# Fake ORS route response — Chicago to LA, ~2000 miles
MOCK_ROUTE_RESPONSE = {
    "features": [{
        "properties": {
            "summary": {"distance": 3240000}  # ~2013 miles in meters
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-87.65, 41.85],   # Chicago (start)
                [-93.00, 41.50],   # Iowa
                [-96.50, 41.00],   # Nebraska
                [-100.0, 40.50],   # ~500 mile mark
                [-104.9, 39.70],   # Colorado
                [-109.0, 38.50],   # Utah border
                [-111.0, 37.50],   # ~1000 mile mark
                [-114.0, 36.50],   # Nevada
                [-117.0, 35.00],   # ~1500 mile mark
                [-118.24, 34.05],  # Los Angeles (end)
            ]
        }
    }]
}

MOCK_CHEAPEST_IL = {"name": "TEST STATION IL", "city": "Marion",    "price": 2.929}
MOCK_CHEAPEST_NE = {"name": "TEST STATION NE", "city": "Waco",      "price": 2.799}
MOCK_CHEAPEST_UT = {"name": "TEST STATION UT", "city": "Riverton",  "price": 3.136}
MOCK_CHEAPEST_CA = {"name": "TEST STATION CA", "city": "Barstow",   "price": 3.899}


class RouteServiceTest(TestCase):

    def _run_service(self, cheapest_side_effect=None):
        """Helper — runs RouteService.plan() with all external calls mocked."""
        cmd = PlanRouteCommand(start="Chicago, IL", end="Los Angeles, CA")

        with patch("apps.routing.application.services.geocode") as mock_geocode, \
             patch("apps.routing.application.services.get_route") as mock_route, \
             patch("apps.routing.application.services.cheapest_in_state") as mock_fuel:

            mock_geocode.side_effect = [
                ([-87.65, 41.85], "Chicago, IL, USA"),
                ([-118.24, 34.05], "Los Angeles, CA, USA"),
            ]
            mock_route.return_value = MOCK_ROUTE_RESPONSE
            mock_fuel.side_effect   = cheapest_side_effect or [
                MOCK_CHEAPEST_IL,  # start fill-up
                MOCK_CHEAPEST_NE,  # stop 1
                MOCK_CHEAPEST_UT,  # stop 2
                MOCK_CHEAPEST_CA,  # final leg
            ]

            return RouteService().plan(cmd)

    def test_returns_route_domain_object(self):
        """Service should return a Route instance."""
        result = self._run_service()
        self.assertIsInstance(result, Route)

    def test_route_has_correct_start_and_end(self):
        """Start and end labels should match geocoder response."""
        result = self._run_service()
        self.assertEqual(result.start, "Chicago, IL, USA")
        self.assertEqual(result.end,   "Los Angeles, CA, USA")

    def test_total_miles_calculated_correctly(self):
        """Total miles should be meters from ORS converted to miles."""
        result = self._run_service()
        # 3,240,000 meters / 1609.34 = ~2013 miles
        self.assertAlmostEqual(result.total_miles, 2013.2, delta=1.0)

    def test_fuel_stops_are_fuel_stop_instances(self):
        """Every stop in fuel_stops should be a FuelStop dataclass."""
        result = self._run_service()
        for stop in result.fuel_stops:
            self.assertIsInstance(stop, FuelStop)

    def test_fuel_stops_spaced_500_miles_apart(self):
        """No two consecutive stops should be less than 400 miles apart."""
        result = self._run_service()
        if len(result.fuel_stops) > 1:
            for i in range(1, len(result.fuel_stops)):
                gap = result.fuel_stops[i].miles_into_route - result.fuel_stops[i-1].miles_into_route
                self.assertGreaterEqual(gap, 400)

    def test_no_stop_placed_within_50_miles_of_end(self):
        """A fuel stop should never be placed in the final 50 miles."""
        result = self._run_service()
        for stop in result.fuel_stops:
            self.assertLess(stop.miles_into_route, result.total_miles - 50)

    def test_cost_breakdown_covers_all_stops(self):
        """Breakdown should have start + en-route stops + final leg entries."""
        result = self._run_service()
        # start fill-up + en-route stops + final leg
        expected = 1 + len(result.fuel_stops) + 1
        self.assertEqual(len(result.cost_breakdown), expected)

    def test_total_cost_matches_breakdown_sum(self):
        """Total cost should equal the sum of all breakdown line items."""
        result     = self._run_service()
        breakdown_sum = round(sum(b["cost"] for b in result.cost_breakdown), 2)
        self.assertAlmostEqual(result.total_cost, breakdown_sum, delta=0.10)

    def test_each_stop_uses_cheapest_station(self):
        """Each stop's price should match what cheapest_in_state returned."""
        result = self._run_service()
        prices = [MOCK_CHEAPEST_NE["price"], MOCK_CHEAPEST_UT["price"]]
        for stop, expected_price in zip(result.fuel_stops, prices):
            self.assertEqual(stop.price_per_gallon, expected_price)

    def test_geometry_returned_in_response(self):
        """Route geometry should be a GeoJSON LineString."""
        result = self._run_service()
        self.assertEqual(result.geometry["type"], "LineString")
        self.assertIn("coordinates", result.geometry)

    def test_no_stops_on_short_route(self):
        """A route under 500 miles should have no en-route fuel stops."""
        short_route = {
            "features": [{
                "properties": {"summary": {"distance": 400000}},  # ~248 miles
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.65, 41.85], [-88.00, 41.00]]
                }
            }]
        }
        cmd = PlanRouteCommand(start="Chicago, IL", end="Springfield, IL")

        with patch("apps.routing.application.services.geocode") as mock_geocode, \
             patch("apps.routing.application.services.get_route") as mock_route, \
             patch("apps.routing.application.services.cheapest_in_state") as mock_fuel:

            mock_geocode.side_effect = [
                ([-87.65, 41.85], "Chicago, IL, USA"),
                ([-88.00, 41.00], "Springfield, IL, USA"),
            ]
            mock_route.return_value = short_route
            mock_fuel.return_value  = MOCK_CHEAPEST_IL

            result = RouteService().plan(cmd)
            self.assertEqual(len(result.fuel_stops), 0)
