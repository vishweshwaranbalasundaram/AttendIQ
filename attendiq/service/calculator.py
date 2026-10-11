"""AttendanceCalculator: the maths behind percentage, recovery and safe bunks.

Let a = classes attended (P + OD) and t = total classes held, threshold = T%.
  percentage      = a / t * 100
  classes needed  = smallest x >= 0 with (a + x) / (t + x) >= T/100   -> ceil((T*t - 100a) / (100 - T))
  safe bunks      = largest  y >= 0 with  a / (t + y)      >= T/100   -> floor(100a / T - t)
For T = 75 these reduce to ceil(3t - 4a) and floor(4a/3 - t).
Fractions are used so there are no floating-point edge cases.
"""
import math
from fractions import Fraction

from attendiq import config


class AttendanceCalculator:
    def __init__(self, threshold: float = None, warning_band: float = None):
        self.threshold = Fraction(str(threshold if threshold is not None else config.THRESHOLD))
        self.warning_band = Fraction(str(warning_band if warning_band is not None else config.WARNING_BAND))
        if not (0 < self.threshold < 100):
            raise ValueError("threshold must be between 0 and 100 (exclusive)")

    def percentage(self, attended: int, total: int) -> float:
        return 0.0 if total <= 0 else round(attended * 100 / total, 2)

    def classes_needed(self, attended: int, total: int) -> int:
        """Consecutive classes to attend to reach the threshold (0 if already safe)."""
        num = self.threshold * total - 100 * attended
        den = 100 - self.threshold
        return max(0, math.ceil(num / den))

    def safe_bunks(self, attended: int, total: int) -> int:
        """Classes that can still be missed while staying at or above the threshold."""
        if attended <= 0:
            return 0
        return max(0, math.floor(Fraction(100 * attended) / self.threshold - total))

    def status(self, attended: int, total: int) -> str:
        if total <= 0:
            return "No data"
        pct = Fraction(attended * 100, total)
        if pct < self.threshold:
            return "Shortage"
        if pct < self.warning_band:
            return "Warning"
        return "Safe"

    def what_if(self, attended: int, total: int, miss: int = 0, attend: int = 0) -> dict:
        """Project the numbers after missing `miss` more classes and attending `attend` more."""
        a2, t2 = attended + attend, total + miss + attend
        return {
            "attended": a2, "total": t2,
            "percentage": self.percentage(a2, t2),
            "status": self.status(a2, t2),
            "classes_needed": self.classes_needed(a2, t2),
            "safe_bunks": self.safe_bunks(a2, t2),
        }

    def summarize(self, attended: int, total: int) -> dict:
        return {
            "attended": attended, "total": total,
            "percentage": self.percentage(attended, total),
            "status": self.status(attended, total),
            "classes_needed": self.classes_needed(attended, total),
            "safe_bunks": self.safe_bunks(attended, total),
        }
