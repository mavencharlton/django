from django.urls import path
from apps.routing.presentation.views import RouteView

urlpatterns = [
    path("route/", RouteView.as_view(), name="route"),
]
