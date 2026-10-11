from attendiq.agents.base import Agent
from attendiq.dao import AttendanceDAO, RiskDAO


class PredictorAgent(Agent):
    """Projects each student's end-of-semester percentage from recent + overall behaviour.

    predicted_attended = attended + blended_rate * remaining_classes
    blended_rate       = 0.6 * (rate over last WINDOW classes) + 0.4 * (overall rate)
    This is a transparent heuristic, not a trained model: easy to explain in a viva and to swap
    for scikit-learn later.
    """
    name = "PredictorAgent"
    purpose = "Predicts end-of-semester attendance and assigns a risk level."
    WINDOW = 10

    def __init__(self, calculator=None):
        super().__init__(calculator)
        self.attendance = AttendanceDAO()
        self.risk = RiskDAO()

    def predict(self, stat: dict) -> dict:
        attended, total = int(stat["attended"]), int(stat["total"])
        planned = max(int(stat["planned_classes"]), total)
        remaining = planned - total
        history = self.attendance.history(stat["student_id"], stat["subject_id"])
        flags = [1 if h["status"] in ("P", "OD") else 0 for h in history]
        overall = attended / total if total else 0.0
        recent_flags = flags[-self.WINDOW:]
        recent = sum(recent_flags) / len(recent_flags) if recent_flags else overall
        blended = 0.6 * recent + 0.4 * overall
        predicted = (attended + blended * remaining) / planned * 100 if planned else 0.0

        needed = self.calc.classes_needed(attended, total)
        thr, band = float(self.calc.threshold), float(self.calc.warning_band)
        if needed > remaining:
            level = "Critical"       # even perfect attendance from now on cannot reach the threshold
        elif predicted < thr:
            level = "High"
        elif predicted < band:
            level = "Medium"
        else:
            level = "Low"
        return {"predicted_percent": round(predicted, 2), "risk_level": level,
                "recent_rate": round(recent * 100, 1), "overall_rate": round(overall * 100, 1)}

    def run(self, context: dict) -> dict:
        stats = context.get("stats")
        if stats is None:
            stats = self.service.stats(student_ids=context.get("student_ids"))
            context["stats"] = stats
        predictions = []
        for s in stats:
            p = self.predict(s)
            self.risk.upsert(s["student_id"], s["subject_id"], p["predicted_percent"], p["risk_level"])
            predictions.append({**p, "student_id": s["student_id"], "subject_id": s["subject_id"],
                                "student_name": s["student_name"], "subject_name": s["subject_name"]})
        context["predictions"] = predictions
        by_level = {}
        for p in predictions:
            by_level[p["risk_level"]] = by_level.get(p["risk_level"], 0) + 1
        return {"predicted": len(predictions), "by_risk_level": by_level}
