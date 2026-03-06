from rest_framework import serializers


# Input validation for the route endpoint.
# Keeps the view clean — by the time data hits the service,
# it's already been validated here.


class PlanRouteSerializer(serializers.Serializer):
    """Validates the POST /route/ request body.

    Both fields are required — the service cannot run without them.
    """
    start = serializers.CharField(max_length=255)  # e.g. "Chicago, IL"
    end = serializers.CharField(max_length=255)  # e.g. "Los Angeles, CA"
