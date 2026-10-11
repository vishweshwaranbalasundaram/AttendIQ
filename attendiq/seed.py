"""Demo data: 4 faculty, 5 subjects, 12 students, 6 weeks of attendance, login accounts.

    python -m attendiq.seed            # create tables and add demo data (skips if data exists)
    python -m attendiq.seed --reset    # drop everything and start again (SQLite only)

Accounts are DEMO ONLY: admin / admin123, f1..f4 / faculty123, <reg_no> / student123.
"""
import argparse
import datetime as dt
import os
import random

from attendiq import config
from attendiq.dao import (AttendanceDAO, FacultyDAO, SessionDAO, StudentDAO, SubjectDAO, TimetableDAO, UserDAO)
from attendiq.model import AttendanceRecord, ClassSession, Faculty, Student, Subject
from attendiq.util.db import DBConnection

FACULTY = [("Dr. Anitha Raman", "CSE"), ("Prof. Suresh Kumar", "CSE"),
           ("Dr. Lavanya Gopal", "CSE"), ("Prof. Imran Basha", "CSE")]
SUBJECTS = [("DBMS", "Database Management Systems", 0), ("OOPS", "Object Oriented Programming", 1),
            ("DMS", "Discrete Mathematical Structures", 2), ("OS", "Operating Systems", 3),
            ("CN", "Computer Networks", 1)]
NAMES = ["Aarav Kumar", "Diya Sharma", "Karthik Raj", "Meera Nair", "Rohan Iyer", "Sneha Reddy",
         "Arjun Menon", "Priya Das", "Vikram Singh", "Ananya Rao", "Harish Babu", "Lakshmi Priya"]
BASE_RATES = [0.96, 0.92, 0.90, 0.88, 0.85, 0.82, 0.79, 0.76, 0.72, 0.68, 0.62, 0.55]
START = dt.date(2026, 8, 3)   # a Monday
WEEKS = 6


def seed(reset: bool = False, verbose: bool = True) -> dict:
    db = DBConnection.get_instance()
    if reset and db.backend == "sqlite":
        db = DBConnection.reset()
        for t in ["QRToken", "AgentLog", "RecoveryPlan", "RiskPrediction", "Notification", "AppUser", "Timetable",
                  "Attendance", "ClassSession", "Enrollment", "Subject", "Faculty", "Student"]:
            db.execute(f"DROP TABLE IF EXISTS {t}")
    db.init_schema()
    if db.query_one("SELECT 1 AS x FROM Student LIMIT 1"):
        if verbose:
            print("Data already present - nothing seeded (use --reset to start fresh).")
        return {"seeded": False}

    rng = random.Random(42)
    fac_dao, sub_dao, stu_dao, user_dao = FacultyDAO(), SubjectDAO(), StudentDAO(), UserDAO()
    faculty_ids = []
    for i, (name, dept) in enumerate(FACULTY, 1):
        fid = fac_dao.create(Faculty(name, dept, f"f{i}@example.edu"))
        faculty_ids.append(fid)
        user_dao.create(f"f{i}", "faculty123", "faculty", fid)
    user_dao.create("admin", "admin123", "admin", None)

    subjects = []
    for code, name, fi in SUBJECTS:
        s = Subject(name, code, faculty_ids[fi], planned_classes=75)
        sub_dao.create(s)
        subjects.append(s)

    students = []
    for i, name in enumerate(NAMES, 1):
        reg = f"REC24CS{i:03d}"
        s = Student(name, reg, "CSE", 2, f"{name.split()[0].lower()}.{reg.lower()}@example.edu")
        stu_dao.create(s)
        students.append(s)
        user_dao.create(reg.lower(), "student123", "student", s.student_id)
        for sub in subjects:
            sub_dao.enroll(s.student_id, sub.subject_id)

    tt, sess, att = TimetableDAO(), SessionDAO(), AttendanceDAO()
    for day in range(5):                       # Mon-Fri, periods 1-5, each subject once a day
        for period in range(1, 6):
            tt.set_slot(subjects[(day + period * 2) % 5].subject_id, day, period)

    n_sessions = 0
    rows = []
    for week in range(WEEKS):
        for slot in tt.all_slots():
            date = START + dt.timedelta(weeks=week, days=slot["day_of_week"])
            cs = ClassSession(slot["subject_id"], date.isoformat(), slot["period"])
            sess.create(cs)
            n_sessions += 1
            marks = {}
            for st, base in zip(students, BASE_RATES):
                rate = min(0.99, max(0.30, base + rng.uniform(-0.08, 0.08)))
                if rng.random() < rate:
                    marks[st.student_id] = "OD" if rng.random() < 0.05 else "P"
                else:
                    marks[st.student_id] = "A"
            stamp = f"{date.isoformat()} 10:00:00"
            rows += [(cs.session_id, sid, status, stamp, 'faculty') for sid, status in marks.items()]

    db.execute_many("INSERT INTO Attendance (session_id, student_id, status, marked_at, marked_via) "
                    "VALUES (%s, %s, %s, %s, %s)", rows)

    if verbose:
        print(f"Seeded {len(FACULTY)} faculty, {len(subjects)} subjects, {len(students)} students, "
              f"{n_sessions} sessions.")
        print("DEMO logins -> admin/admin123 | f1../faculty123 | student reg no (lowercase), e.g. "
              "rec24cs001/student123")
    return {"seeded": True, "sessions": n_sessions}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    seed(ap.parse_args().reset)
