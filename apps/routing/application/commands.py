from dataclasses import dataclass


@dataclass
class PlanRouteCommand:
    """Carries the user's input into the service layer.
    """
    start: str  # e.g. "Chicago, IL"
    end: str    # e.g. "Los Angeles, CA"
