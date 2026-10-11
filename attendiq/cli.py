"""Console menu app: the whole system without the API or UI (handy for the viva demo).

    python -m attendiq.cli
"""
import datetime as dt

from attendiq.agents import AgentOrchestrator, ChatAgent
from attendiq.dao import AttendanceDAO, SessionDAO, StudentDAO, SubjectDAO
from attendiq.model import ClassSession, Student
from attendiq.report import AttendanceReport, ShortageReport, SubjectSummaryReport
from attendiq.seed import seed
from attendiq.util.db import DBConnection

MENU = """
==== AttendIQ ====
 1. List students           7. Student attendance report
 2. Add student             8. Shortage report
 3. Update student          9. Subject-wise summary
 4. Delete student         10. Run all agents
 5. List subjects          11. Chat with the assistant
 6. Mark attendance         0. Exit
"""


def ask(prompt, default=None):
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def pick_student(dao):
    reg = ask("Student reg no")
    s = dao.get_by_reg(reg or "")
    if not s:
        print("  No such student.")
    return s


def list_students(dao):
    for s in dao.list_all():
        print(f"  {s.student_id:>3}  {s.reg_no:<12} {s.name:<20} {s.department} Y{s.year}  {s.email}")


def add_student(dao):
    try:
        s = Student(ask("Name"), ask("Reg no"), ask("Department", "CSE"), int(ask("Year", "2")), ask("Email"))
        dao.create(s)
        print(f"  Added with id {s.student_id}.")
    except Exception as exc:
        print(f"  Could not add: {exc}")


def update_student(dao):
    s = pick_student(dao)
    if s:
        try:
            s.name = ask("Name", s.name)
            s.department = ask("Department", s.department)
            s.year = int(ask("Year", str(s.year)))
            s.email = ask("Email", s.email)
            dao.update(s)
            print("  Updated.")
        except Exception as exc:
            print(f"  Could not update: {exc}")


def delete_student(dao):
    s = pick_student(dao)
    if s and ask(f"Delete {s.name} and all their attendance? (yes/no)", "no") == "yes":
        dao.delete(s.student_id)
        print("  Deleted.")


def mark_attendance(subjects, sessions, attendance, orch):
    for s in subjects.list_all():
        print(f"  {s.subject_id}. {s.subject_code or ''} {s.subject_name}")
    try:
        subject_id = int(ask("Subject id"))
        date = ask("Date (YYYY-MM-DD)", dt.date.today().isoformat())
        dt.date.fromisoformat(date)
        period = int(ask("Period", "1"))
    except (TypeError, ValueError):
        print("  Invalid input.")
        return
    cs = sessions.find(subject_id, date, period)
    if not cs:
        cs = ClassSession(subject_id, date, period)
        sessions.create(cs)
    roster = attendance.roster(cs.session_id)
    if not roster:
        print("  No students are enrolled in that subject.")
        return
    print("  Everyone defaults to Present. Enter exceptions as REGNO:A or REGNO:OD, comma separated.")
    marks = {r["student_id"]: "P" for r in roster}
    by_reg = {r["reg_no"].upper(): r["student_id"] for r in roster}
    for item in filter(None, (ask("Exceptions", "") or "").split(",")):
        try:
            reg, status = item.strip().upper().split(":")
            marks[by_reg[reg]] = status
            assert status in ("A", "OD")
        except (ValueError, KeyError, AssertionError):
            print(f"  Skipped '{item}'.")
    written = attendance.bulk_mark(cs.session_id, marks)
    print(f"  Marked {len(written)} students. Agents running...")
    out = orch.on_attendance_marked(written)
    print("  ", {k: v for k, v in out.items() if k != "findings"})


def chat(students):
    who = ask("Chat as (reg no for a student, or blank for admin)", "")
    if who:
        s = students.get_by_reg(who)
        if not s:
            print("  No such student.")
            return
        agent = ChatAgent(role="student", linked_id=s.student_id)
    else:
        agent = ChatAgent(role="admin")
    print("  Type 'back' to return.")
    while True:
        q = input("  you> ").strip()
        if q.lower() in ("back", "exit", ""):
            return
        r = agent.chat(q)
        print(f"  [{r['mode']}] {r['reply']}")


def main():
    db = DBConnection.get_instance()
    db.init_schema()
    if not db.query_one("SELECT 1 AS x FROM Student LIMIT 1"):
        seed()
    students, subjects, sessions, attendance = StudentDAO(), SubjectDAO(), SessionDAO(), AttendanceDAO()
    orch = AgentOrchestrator()
    while True:
        print(MENU)
        choice = ask("Choose")
        if choice == "0" or choice is None:
            break
        elif choice == "1": list_students(students)
        elif choice == "2": add_student(students)
        elif choice == "3": update_student(students)
        elif choice == "4": delete_student(students)
        elif choice == "5":
            for s in subjects.list_all():
                print(f"  {s.subject_id}. {s.subject_code or '':<5} {s.subject_name} ({s.planned_classes} planned)")
        elif choice == "6": mark_attendance(subjects, sessions, attendance, orch)
        elif choice == "7":
            s = pick_student(students)
            if s:
                print(AttendanceReport(s.student_id).render_text())
        elif choice == "8": print(ShortageReport().render_text())
        elif choice == "9": print(SubjectSummaryReport().render_text())
        elif choice == "10":
            out = orch.run_all()
            for k, v in out.items():
                if k == "findings":
                    for f in v:
                        print(f"   [{f['severity']}] {f['detail']}")
                else:
                    print(f"  {k}: {v}")
        elif choice == "11": chat(students)
        else:
            print("  Unknown option.")


if __name__ == "__main__":
    main()
