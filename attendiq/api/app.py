"""FastAPI REST layer. Run:  uvicorn attendiq.api.app:app --reload"""
import datetime as dt
import os
import secrets
from typing import Dict, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from attendiq import config
from attendiq.agents import AgentOrchestrator, ChatAgent
from attendiq.api.auth import create_token, current_user, require
from attendiq.dao import (AgentLogDAO, AttendanceDAO, FacultyDAO, NotificationDAO, PlanDAO, QRTokenDAO, RiskDAO,
                          SessionDAO, StudentDAO, SubjectDAO, TimetableDAO, UserDAO)
from attendiq.model import ClassSession, Faculty, Student, Subject, VALID_STATUS
from attendiq.report import AttendanceReport, ShortageReport, SubjectSummaryReport
from attendiq.service.attendance_service import AttendanceService
from attendiq.util.db import DBConnection

QR_SECONDS = 90


class LoginIn(BaseModel):
    username: str
    password: str


class StudentIn(BaseModel):
    name: str
    reg_no: str
    department: Optional[str] = None
    year: Optional[int] = None
    email: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class FacultyIn(BaseModel):
    name: str
    department: Optional[str] = None
    email: Optional[str] = None


class SubjectIn(BaseModel):
    subject_name: str
    subject_code: Optional[str] = None
    faculty_id: Optional[int] = None
    planned_classes: int = 60


class EnrollIn(BaseModel):
    student_id: int


class SessionIn(BaseModel):
    subject_id: int
    class_date: str
    period: int


class MarksIn(BaseModel):
    marks: Dict[int, str]          # {student_id: "P" | "A" | "OD"}


class ChatIn(BaseModel):
    message: str


class QRScanIn(BaseModel):
    token: str


def _guard_write(fn):
    """Turn model validation errors into 400 and duplicate keys into 409."""
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(409, "Duplicate entry")
        if "foreign key" in msg:
            raise HTTPException(400, "Referenced record does not exist")
        raise


def create_app() -> FastAPI:
    app = FastAPI(title="AttendIQ", version="1.0",
                  description="Agentic AI attendance monitoring, prediction and recovery planning.")
    DBConnection.get_instance().init_schema()
    if os.getenv("ATTENDIQ_AUTOSEED") == "1":
        from attendiq.seed import seed
        seed(verbose=False)

    students, faculty, subjects = StudentDAO(), FacultyDAO(), SubjectDAO()
    sessions, attendance, timetable = SessionDAO(), AttendanceDAO(), TimetableDAO()
    users, qr = UserDAO(), QRTokenDAO()
    service, orchestrator = AttendanceService(), AgentOrchestrator()

    def own_or_any(user: dict, student_id: Optional[int]) -> Optional[int]:
        """Students are always pinned to their own id, whatever they ask for."""
        return user["linked_id"] if user["role"] == "student" else student_id

    def can_teach(user: dict, subject_id: int):
        sub = subjects.get(subject_id)
        if not sub:
            raise HTTPException(404, "Subject not found")
        if user["role"] == "faculty" and sub.faculty_id != user["linked_id"]:
            raise HTTPException(403, "You do not teach this subject")
        return sub

    # ---------------- auth ----------------
    @app.post("/auth/login", tags=["auth"])
    def login(body: LoginIn):
        user = users.authenticate(body.username, body.password)
        if not user:
            raise HTTPException(401, "Wrong username or password")
        return {"access_token": create_token(user), "token_type": "bearer",
                "role": user["role"], "linked_id": user["linked_id"]}

    @app.get("/me", tags=["auth"])
    def me(user: dict = Depends(current_user)):
        detail = None
        if user["role"] == "student":
            s = students.get(user["linked_id"]); detail = s.to_dict() if s else None
        elif user["role"] == "faculty":
            f = faculty.get(user["linked_id"]); detail = f.to_dict() if f else None
        return {**user, "profile": detail}

    # ---------------- students / faculty / subjects (CRUD) ----------------
    @app.get("/students", tags=["students"])
    def list_students(_=Depends(require("admin", "faculty"))):
        return [s.to_dict() for s in students.list_all()]

    @app.post("/students", status_code=201, tags=["students"])
    def create_student(body: StudentIn, _=Depends(require("admin"))):
        def go():
            s = Student(body.name, body.reg_no, body.department, body.year, body.email,
                        telegram_chat_id=body.telegram_chat_id)
            students.create(s)
            return s.to_dict()
        return _guard_write(go)

    @app.get("/students/{student_id}", tags=["students"])
    def get_student(student_id: int, user=Depends(current_user)):
        if user["role"] == "student" and user["linked_id"] != student_id:
            raise HTTPException(403, "You can only view your own record")
        s = students.get(student_id)
        if not s:
            raise HTTPException(404, "Student not found")
        return s.to_dict()

    @app.put("/students/{student_id}", tags=["students"])
    def update_student(student_id: int, body: StudentIn, _=Depends(require("admin"))):
        if not students.get(student_id):
            raise HTTPException(404, "Student not found")

        def go():
            s = Student(body.name, body.reg_no, body.department, body.year, body.email, student_id,
                        body.telegram_chat_id)
            students.update(s)
            return s.to_dict()
        return _guard_write(go)

    @app.delete("/students/{student_id}", status_code=204, tags=["students"])
    def delete_student(student_id: int, _=Depends(require("admin"))):
        if not students.get(student_id):
            raise HTTPException(404, "Student not found")
        students.delete(student_id)

    @app.get("/faculty", tags=["faculty"])
    def list_faculty(_=Depends(require("admin", "faculty"))):
        return [f.to_dict() for f in faculty.list_all()]

    @app.post("/faculty", status_code=201, tags=["faculty"])
    def create_faculty(body: FacultyIn, _=Depends(require("admin"))):
        def go():
            f = Faculty(body.name, body.department, body.email)
            faculty.create(f)
            return f.to_dict()
        return _guard_write(go)

    @app.put("/faculty/{faculty_id}", tags=["faculty"])
    def update_faculty(faculty_id: int, body: FacultyIn, _=Depends(require("admin"))):
        if not faculty.get(faculty_id):
            raise HTTPException(404, "Faculty not found")

        def go():
            f = Faculty(body.name, body.department, body.email, faculty_id)
            faculty.update(f)
            return f.to_dict()
        return _guard_write(go)

    @app.delete("/faculty/{faculty_id}", status_code=204, tags=["faculty"])
    def delete_faculty(faculty_id: int, _=Depends(require("admin"))):
        if not faculty.get(faculty_id):
            raise HTTPException(404, "Faculty not found")
        faculty.delete(faculty_id)

    @app.get("/subjects", tags=["subjects"])
    def list_subjects(_=Depends(current_user)):
        return [s.to_dict() for s in subjects.list_all()]

    @app.post("/subjects", status_code=201, tags=["subjects"])
    def create_subject(body: SubjectIn, _=Depends(require("admin"))):
        def go():
            s = Subject(body.subject_name, body.subject_code, body.faculty_id, body.planned_classes)
            subjects.create(s)
            return s.to_dict()
        return _guard_write(go)

    @app.put("/subjects/{subject_id}", tags=["subjects"])
    def update_subject(subject_id: int, body: SubjectIn, _=Depends(require("admin"))):
        if not subjects.get(subject_id):
            raise HTTPException(404, "Subject not found")

        def go():
            s = Subject(body.subject_name, body.subject_code, body.faculty_id, body.planned_classes, subject_id)
            subjects.update(s)
            return s.to_dict()
        return _guard_write(go)

    @app.delete("/subjects/{subject_id}", status_code=204, tags=["subjects"])
    def delete_subject(subject_id: int, _=Depends(require("admin"))):
        if not subjects.get(subject_id):
            raise HTTPException(404, "Subject not found")
        subjects.delete(subject_id)

    @app.post("/subjects/{subject_id}/enroll", status_code=201, tags=["subjects"])
    def enroll(subject_id: int, body: EnrollIn, _=Depends(require("admin"))):
        if not subjects.get(subject_id) or not students.get(body.student_id):
            raise HTTPException(404, "Student or subject not found")
        subjects.enroll(body.student_id, subject_id)
        return {"enrolled": True}

    @app.get("/timetable", tags=["subjects"])
    def get_timetable(_=Depends(current_user)):
        return timetable.all_slots()

    # ---------------- sessions & attendance ----------------
    @app.post("/sessions", status_code=201, tags=["attendance"])
    def create_session(body: SessionIn, user=Depends(require("admin", "faculty"))):
        can_teach(user, body.subject_id)

        def go():
            dt.date.fromisoformat(body.class_date)          # validates the date
            cs = ClassSession(body.subject_id, body.class_date, body.period)
            sessions.create(cs)
            return {**cs.to_dict(), "roster": attendance.roster(cs.session_id)}
        return _guard_write(go)

    @app.get("/sessions/{session_id}/roster", tags=["attendance"])
    def roster(session_id: int, user=Depends(require("admin", "faculty"))):
        cs = sessions.get(session_id)
        if not cs:
            raise HTTPException(404, "Session not found")
        can_teach(user, cs.subject_id)
        return attendance.roster(session_id)

    @app.put("/sessions/{session_id}/attendance", tags=["attendance"])
    def mark_attendance(session_id: int, body: MarksIn, user=Depends(require("admin", "faculty"))):
        cs = sessions.get(session_id)
        if not cs:
            raise HTTPException(404, "Session not found")
        can_teach(user, cs.subject_id)
        enrolled = set(subjects.student_ids_for_subject(cs.subject_id))
        for sid, status in body.marks.items():
            if status not in VALID_STATUS:
                raise HTTPException(400, f"Invalid status '{status}' (use P, A or OD)")
            if sid not in enrolled:
                raise HTTPException(400, f"Student {sid} is not enrolled in this subject")
        written = attendance.bulk_mark(session_id, body.marks, via="faculty")
        agent_summary = orchestrator.on_attendance_marked(written)     # agents react automatically
        return {"marked": len(written), "agents": agent_summary}

    @app.delete("/sessions/{session_id}/attendance/{student_id}", status_code=204, tags=["attendance"])
    def delete_mark(session_id: int, student_id: int, user=Depends(require("admin", "faculty"))):
        cs = sessions.get(session_id)
        if not cs:
            raise HTTPException(404, "Session not found")
        can_teach(user, cs.subject_id)
        attendance.delete(session_id, student_id)
        orchestrator.on_attendance_marked([student_id])

    @app.get("/attendance/summary", tags=["attendance"])
    def summary(student_id: Optional[int] = None, subject_id: Optional[int] = None, user=Depends(current_user)):
        return service.stats(student_id=own_or_any(user, student_id), subject_id=subject_id)

    # ---------------- QR attendance ----------------
    @app.post("/sessions/{session_id}/qr", tags=["qr"])
    def make_qr(session_id: int, user=Depends(require("admin", "faculty"))):
        cs = sessions.get(session_id)
        if not cs:
            raise HTTPException(404, "Session not found")
        can_teach(user, cs.subject_id)
        token = secrets.token_urlsafe(8)
        expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=QR_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
        qr.create(session_id, token, expires)
        return {"token": token, "payload": f"attendiq:{token}", "expires_at": expires, "valid_seconds": QR_SECONDS}

    @app.post("/attendance/qr-scan", tags=["qr"])
    def qr_scan(body: QRScanIn, user=Depends(require("student"))):
        row = qr.get_valid(body.token.removeprefix("attendiq:"))
        if not row:
            raise HTTPException(400, "QR code is invalid or expired")
        cs = sessions.get(row["session_id"])
        if user["linked_id"] not in set(subjects.student_ids_for_subject(cs.subject_id)):
            raise HTTPException(403, "You are not enrolled in this subject")
        from attendiq.model import AttendanceRecord
        attendance.mark(AttendanceRecord(cs.session_id, user["linked_id"], "P", marked_via="qr"))
        agent_summary = orchestrator.on_attendance_marked([user["linked_id"]])
        return {"marked": "P", "session_id": cs.session_id, "agents": agent_summary}

    # ---------------- reports ----------------
    @app.get("/reports/{kind}", tags=["reports"])
    def report(kind: str, student_id: Optional[int] = None, subject_id: Optional[int] = None,
               user=Depends(current_user)):
        if kind == "attendance":
            sid = own_or_any(user, student_id)
            if sid is None:
                raise HTTPException(400, "student_id is required")
            return AttendanceReport(sid).generate()
        if user["role"] == "student":
            raise HTTPException(403, "Faculty/admin only")
        if kind == "shortage":
            return ShortageReport(subject_id).generate()
        if kind == "subject-summary":
            return SubjectSummaryReport().generate()
        raise HTTPException(404, "Unknown report (attendance | shortage | subject-summary)")

    # ---------------- agents ----------------
    @app.post("/agents/run", tags=["agents"])
    def run_agents(user=Depends(require("admin", "faculty"))):
        return orchestrator.run_all()

    @app.get("/agents", tags=["agents"])
    def list_agents(_=Depends(current_user)):
        return orchestrator.describe()

    @app.get("/agents/log", tags=["agents"])
    def agent_log(limit: int = 50, agent: Optional[str] = None, _=Depends(require("admin", "faculty"))):
        return AgentLogDAO().recent(min(limit, 200), agent)

    @app.get("/predictions", tags=["agents"])
    def predictions(student_id: Optional[int] = None, user=Depends(current_user)):
        return RiskDAO().list(own_or_any(user, student_id))

    @app.get("/plans", tags=["agents"])
    def plans(student_id: Optional[int] = None, user=Depends(current_user)):
        return PlanDAO().list(own_or_any(user, student_id))

    @app.get("/notifications", tags=["agents"])
    def notifications(student_id: Optional[int] = None, user=Depends(current_user)):
        if user["role"] == "student":
            return NotificationDAO().list(student_id=user["linked_id"], audience="student")
        return NotificationDAO().list(student_id=student_id)

    @app.post("/chat", tags=["agents"])
    def chat(body: ChatIn, user=Depends(current_user)):
        if not body.message.strip():
            raise HTTPException(400, "Empty message")
        return ChatAgent(role=user["role"], linked_id=user["linked_id"]).chat(body.message[:1000])

    return app


app = create_app()
