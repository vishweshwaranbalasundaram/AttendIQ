from attendiq.agents.anomaly import AnomalyAgent
from attendiq.agents.monitor import MonitorAgent
from attendiq.agents.notifier import NotifierAgent
from attendiq.agents.planner import PlannerAgent
from attendiq.agents.predictor import PredictorAgent
from attendiq.service.calculator import AttendanceCalculator


class AgentOrchestrator:
    """Runs the agent pipeline: Monitor -> Predictor -> Planner -> Anomaly -> Notifier.

    The pipeline only reads attendance and writes predictions, plans, notifications and logs.
    It NEVER changes attendance marks - only faculty can do that.
    """

    def __init__(self, calculator: AttendanceCalculator = None):
        calc = calculator or AttendanceCalculator()
        self.pipeline = [MonitorAgent(calc), PredictorAgent(calc), PlannerAgent(calc),
                         AnomalyAgent(calc), NotifierAgent(calc)]

    def run_all(self, student_ids: list = None) -> dict:
        context = {"student_ids": student_ids}
        summary = {agent.name: agent.execute(context) for agent in self.pipeline}
        summary["findings"] = context.get("findings", [])
        return summary

    def on_attendance_marked(self, student_ids: list) -> dict:
        """Event hook: called by the API right after faculty mark attendance."""
        return self.run_all(sorted(set(student_ids)))

    def describe(self) -> list:
        return [a.describe() for a in self.pipeline]
