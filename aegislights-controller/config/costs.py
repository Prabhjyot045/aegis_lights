"""Edge cost function coefficients."""

from dataclasses import dataclass


@dataclass
class CostConfig:
    """Configuration for edge cost calculation: we(t) = a·delay + b·queue + c·spillback + d·incident."""
    
    # Cost coefficients (all > 0)
    delay_weight: float = 1.0       # Weight for delay (seconds/vehicle)
    queue_weight: float = 0.5       # Weight for queue length (vehicles)
    spillback_weight: float = 10.0  # Penalty for spillback (boolean indicator)
    incident_weight: float = 20.0   # Penalty for incident (boolean indicator)
    
    # Normalization factors (to bring all metrics to similar scale)
    delay_normalization: float = 1.0
    queue_normalization: float = 1.0
    
    def get_coefficients(self) -> tuple[float, float, float, float]:
        """Return coefficients as tuple (a, b, c, d)."""
        return (
            self.delay_weight,
            self.queue_weight,
            self.spillback_weight,
            self.incident_weight
        )
