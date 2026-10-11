from attendiq.agents.base import Agent
from attendiq.dao import AttendanceDAO, StudentDAO


class AnomalyAgent(Agent):
    """Rule-based proxy / data-entry anomaly detector (deterministic and explainable)."""
    name = "AnomalyAgent"
    purpose = "Flags impossible or suspicious attendance patterns for faculty review."
    OD_RATIO = 0.30      # share of 'present' marks that are OD
    PERFECT_MIN = 10     # classes this big with 100% present look unusual

    def __init__(self, calculator=None):
        super().__init__(calculator)
        self.attendance = AttendanceDAO()
        self.students = StudentDAO()

    def run(self, context: dict) -> dict:
        findings = []
        names = {}

        def student_name(sid):
            if sid not in names:
                s = self.students.get(sid)
                names[sid] = s.name if s else f"#{sid}"
            return names[sid]

        for r in self.attendance.simultaneous_presence():
            findings.append({
                "type": "impossible_presence", "severity": "high", "student_id": r["student_id"],
                "detail": f"{student_name(r['student_id'])} is marked Present in {r['n']} subjects at the same "
                          f"time ({r['class_date']}, period {r['period']})."})

        for r in self.attendance.session_marks():
            if r["marked"] >= self.PERFECT_MIN and r["present"] == r["marked"]:
                findings.append({
                    "type": "perfect_session", "severity": "low", "session_id": r["session_id"],
                    "detail": f"Session {r['session_id']} ({r['class_date']}, period {r['period']}): all "
                              f"{r['marked']} students marked Present - worth a quick check."})

        for r in self.attendance.summary_rows():
            if r["attended"] >= 5 and r["od_count"] / r["attended"] > self.OD_RATIO:
                findings.append({
                    "type": "high_od_usage", "severity": "medium", "student_id": r["student_id"],
                    "detail": f"{r['student_name']} has {r['od_count']} OD marks out of {r['attended']} present "
                              f"in {r['subject_name']} ({r['od_count'] * 100 // r['attended']}%)."})

        context["findings"] = findings
        return {"findings": len(findings), "high": sum(1 for f in findings if f["severity"] == "high")}
