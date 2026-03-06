import json
import urllib.request
import urllib.parse
from django.conf import settings


def _api_key():
    return settings.OPENROUTE_API_KEY


def geocode(place: str) -> tuple[list, str]:
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


def reverse_geocode(lon: float, lat: float) -> str:
    url = (
        "https://api.openrouteservice.org/geocode/reverse?"
        + urllib.parse.urlencode({
            "api_key":   _api_key(),
            "point.lon": lon,
            "point.lat": lat,
            "size":      1,
        })
    )
    try:
        with urllib.request.urlopen(url) as r:
            data = json.loads(r.read())
        props = data["features"][0]["properties"]
        return props.get("region_a") or props.get("region", "")[:2].upper()
    except Exception:
        return ""


def get_route(start_coords: list, end_coords: list) -> dict:
    url     = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    payload = json.dumps({"coordinates": [start_coords, end_coords]}).encode()
    req     = urllib.request.Request(
        url,
        data    = payload,
        headers = {
            "Authorization": _api_key(),
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())
