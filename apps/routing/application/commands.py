from dataclasses import dataclass


@dataclass
class PlanRouteCommand:
    start: str
    end: str
