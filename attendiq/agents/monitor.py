from attendiq.agents.base import Agent


class MonitorAgent(Agent):
    name = "MonitorAgent"
    purpose = "Recalculates percentages and flags Shortage / Warning / Safe."

    def run(self, context: dict) -> dict:
        stats = self.service.stats(student_ids=context.get("student_ids"))
        context["stats"] = stats
        context["alerts"] = [s for s in stats if s["status"] in ("Shortage", "Warning")]
        return {
            "checked": len(stats),
            "shortage": sum(1 for s in stats if s["status"] == "Shortage"),
            "warning": sum(1 for s in stats if s["status"] == "Warning"),
        }
