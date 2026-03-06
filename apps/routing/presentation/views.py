import time
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.routing.application.commands import PlanRouteCommand
from apps.routing.application.services import RouteService
from apps.routing.presentation.serializers import PlanRouteSerializer


class RouteView(APIView):
    """Single view handling both the UI and the API.

    GET  /route/ — serves the Leaflet map UI
    POST /route/ — accepts {start, end}, returns route + fuel stops + cost
    """

    def get(self, request):
        # Just render the map page — all the logic happens on POST
        return render(request, "routing/map.html")

    def post(self, request):
        serializer = PlanRouteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Time the full service call for the meta response
        t0 = time.perf_counter()
        cmd = PlanRouteCommand(**serializer.validated_data)
        result = RouteService().plan(cmd)
        elapsed = round(time.perf_counter() - t0, 2)

        return Response({
            "start":          result.start,
            "end":            result.end,
            "total_miles":    result.total_miles,
            "total_cost":     result.total_cost,
            "fuel_stops":     [vars(s) for s in result.fuel_stops],
            "cost_breakdown": result.cost_breakdown,
            "geometry":       result.geometry,
            "meta": {
                "elapsed_seconds": elapsed,
                "api_calls":       3,  # geocode start, geocode end, get route
            }
        })
