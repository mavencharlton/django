import json
import urllib.request
import urllib.parse
from django.conf import settings


# All communication with the OpenRouteService API lives here.
# The rest of the app never imports urllib or knows about ORS directly.
# 3 calls per request: geocode start, geocode end, get route.


def _api_key():
    """Pull the ORS key from settings at call time, not at import time."""
    return settings.OPENROUTE_API_KEY


def geocode(place: str) -> tuple[list, str]:
    """Convert a place name to [long, lat] coordinates.

    Restricts results to the US and returns the first match.
    Also returns the full display label for use in the response.
    """
    url = (
        "https://api.openrouteservice.org/geocode/search?"
        + urllib.parse.urlencode({
            "api_key":          _api_key(),
            "text":             place,
            "boundary.country": "US",
            "size":             1,
        })
    )
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())
    feature = data["features"][0]
    return feature["geometry"]["coordinates"], feature["properties"]["label"]


def get_route(start_coords: list, end_coords: list) -> dict:
    """Fetch a driving route between two coordinate pairs.

    Returns GeoJSON with the full route geometry and summary distance.
    Using the /geojson endpoint so coordinates come back as a proper
    list rather than an encoded polyline string.
    """
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    payload = json.dumps({"coordinates": [start_coords, end_coords]}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": _api_key(),
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())
