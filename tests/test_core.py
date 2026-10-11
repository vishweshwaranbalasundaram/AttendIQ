import pytest
from attendiq.agents import AgentOrchestrator, AnomalyAgent, MonitorAgent, PredictorAgent
from attendiq.agents.base import Agent
from attendiq.dao import (AgentLogDAO, AttendanceDAO, NotificationDAO, PlanDAO, RiskDAO, SessionDAO, StudentDAO,
                          SubjectDAO, UserDAO)
from attendiq.model import AttendanceRecord, ClassSession, Faculty, Person, Student
from attendiq.report import AttendanceReport, ShortageReport, SubjectSummaryReport
from attendiq.util.db import DBConnection


def test_singleton():
    assert DBConnection.get_instance() is DBConnection.get_instance()


def test_inheritance_and_validation():
    s = Student("Test User", "X1", "CSE", 2, "t@example.edu")
    assert isinstance(s, Person) and s.role() == "student"
    assert Faculty("F").role() == "faculty"
    with pytest.raises(ValueError):
        Student("", "X2")
    with pytest.raises(ValueError):
        Student("A", "X3", email="not-an-email")
    with pytest.raises(ValueError):
        AttendanceRecord(1, 1, "LATE")


def test_student_crud():
    dao = StudentDAO()
    n = len(dao.list_all())
    s = Student("New Kid", "NEW001", "CSE", 2, "new@example.edu")
    dao.create(s)
    assert dao.get(s.student_id).name == "New Kid" and len(dao.list_all()) == n + 1
    s.name = "Renamed"
    dao.update(s)
    assert dao.get_by_reg("NEW001").name == "Renamed"
    dao.delete(s.student_id)
    assert dao.get(s.student_id) is None


def test_unique_constraints():
    sessions = SessionDAO()
    first = sessions.list_for_subject(1)[0]
    with pytest.raises(Exception):
        sessions.create(ClassSession(first.subject_id, first.class_date, first.period))   # duplicate
    with pytest.raises(Exception):
        StudentDAO().create(Student("Dup", "REC24CS001"))                                   # duplicate reg_no


def test_cascade_delete_student_removes_attendance():
    att = AttendanceDAO()
    assert att.summary_rows(student_id=1)
    StudentDAO().delete(1)
    assert att.summary_rows(student_id=1) == []


def test_passwords_hashed_and_verified():
    u = UserDAO().get_by_username("admin")
    assert "admin123" not in u["password_hash"]
    assert UserDAO().authenticate("admin", "admin123")
    assert UserDAO().authenticate("admin", "wrong") is None


def test_mark_is_upsert():
    att = AttendanceDAO()
    session_id = SessionDAO().list_for_subject(1)[0].session_id
    att.mark(AttendanceRecord(session_id, 1, "A"))
    att.mark(AttendanceRecord(session_id, 1, "P"))
    rows = [r for r in att.roster(session_id) if r["student_id"] == 1]
    assert rows[0]["status"] == "P"


def test_monitor_flags_low_attenders():
    ctx = {"student_ids": None}
    res = MonitorAgent().execute(ctx)
    assert res["shortage"] > 0 and res["checked"] == 12 * 5
    lowest = min(ctx["stats"], key=lambda s: s["percentage"])
    assert lowest["status"] == "Shortage" and lowest["classes_needed"] > 0


def test_pipeline_end_to_end_and_audit_log():
    out = AgentOrchestrator().run_all()
    assert "error" not in str(out["MonitorAgent"]) and out["NotifierAgent"]["students_alerted"] > 0
    assert RiskDAO().list() and PlanDAO().list() and NotificationDAO().list()
    names = {r["agent_name"] for r in AgentLogDAO().recent(100)}
    assert {"MonitorAgent", "PredictorAgent", "PlannerAgent", "AnomalyAgent", "NotifierAgent"} <= names


def test_notifications_deduplicated_same_day():
    orch = AgentOrchestrator()
    first = orch.run_all()["NotifierAgent"]["students_alerted"]
    second = orch.run_all()
    assert first > 0 and second["NotifierAgent"]["students_alerted"] == 0
    assert second["NotifierAgent"]["duplicates_skipped"] == first


def test_critical_risk_when_recovery_impossible():
    # tiny remaining runway: 30 attended of 40, planned 41 -> cannot hit 75% after many absences
    ctx = {"stats": [{"student_id": 1, "subject_id": 1, "student_name": "x", "subject_name": "y",
                      "attended": 10, "total": 40, "planned_classes": 45}]}
    pa = PredictorAgent()
    assert pa.predict(ctx["stats"][0])["risk_level"] == "Critical"


def test_escalation_to_faculty_for_worst_student():
    AgentOrchestrator().run_all()
    faculty_msgs = NotificationDAO().list(audience="faculty")
    assert faculty_msgs and "ESCALATION" in faculty_msgs[0]["message"]


def test_agents_never_change_attendance_marks():
    att = AttendanceDAO()
    before = att.db.query("SELECT session_id, student_id, status FROM Attendance ORDER BY attendance_id")
    AgentOrchestrator().run_all()
    after = att.db.query("SELECT session_id, student_id, status FROM Attendance ORDER BY attendance_id")
    assert before == after


def test_agent_failure_is_contained_and_logged():
    class Broken(Agent):
        name = "Broken"
        def run(self, context):
            raise RuntimeError("boom")
    assert "error" in Broken().execute({})
    assert any(r["action"] == "error" for r in AgentLogDAO().recent(5, "Broken"))


def test_anomaly_detects_impossible_presence():
    att, sess = AttendanceDAO(), SessionDAO()
    s1 = sess.list_for_subject(1)[0]
    # create a second session in a different subject at the very same date+period and mark student 1 present in both
    other = SessionDAO()
    clash = ClassSession(2, s1.class_date, s1.period)
    other.create(clash)
    att.mark(AttendanceRecord(s1.session_id, 1, "P"))
    att.mark(AttendanceRecord(clash.session_id, 1, "P"))
    ctx = {}
    AnomalyAgent().execute(ctx)
    assert any(f["type"] == "impossible_presence" and f["student_id"] == 1 for f in ctx["findings"])


def test_reports():
    assert AttendanceReport(1).generate()["rows"]
    text = ShortageReport().render_text()
    assert "Shortage report" in text and "|" in text
    summary = SubjectSummaryReport().generate()
    assert len(summary["rows"]) == 5


def test_reg_no_lookup_is_case_insensitive():
    assert StudentDAO().get_by_reg("rec24cs012").name == StudentDAO().get_by_reg("REC24CS012").name
