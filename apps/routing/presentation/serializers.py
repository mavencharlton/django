from rest_framework import serializers


class PlanRouteSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=255)
    end   = serializers.CharField(max_length=255)
