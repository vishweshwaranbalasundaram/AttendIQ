"""SubjectDAO, SessionDAO, AttendanceDAO, TimetableDAO."""
from attendiq.dao.base import BaseDAO
from attendiq.model import Subject, ClassSession, AttendanceRecord
from attendiq.util.db import now_str


class SubjectDAO(BaseDAO):
    def create(self, s: Subject) -> int:
        s.subject_id = self.db.execute(
            "INSERT INTO Subject (subject_code, subject_name, faculty_id, planned_classes) VALUES (%s, %s, %s, %s)",
            (s.subject_code, s.subject_name, s.faculty_id, s.planned_classes))
        return s.subject_id

    def get(self, subject_id: int):
        r = self.db.query_one("SELECT * FROM Subject WHERE subject_id = %s", (subject_id,))
        return Subject.from_row(r) if r else None

    def list_all(self) -> list:
        return [Subject.from_row(r) for r in self.db.query("SELECT * FROM Subject ORDER BY subject_name")]

    def list_for_faculty(self, faculty_id: int) -> list:
        rows = self.db.query("SELECT * FROM Subject WHERE faculty_id = %s ORDER BY subject_name", (faculty_id,))
        return [Subject.from_row(r) for r in rows]

    def update(self, s: Subject) -> None:
        self.db.execute(
            "UPDATE Subject SET subject_code=%s, subject_name=%s, faculty_id=%s, planned_classes=%s WHERE subject_id=%s",
            (s.subject_code, s.subject_name, s.faculty_id, s.planned_classes, s.subject_id))

    def delete(self, subject_id: int) -> None:
        self.db.execute("DELETE FROM Subject WHERE subject_id = %s", (subject_id,))

    # --- enrollment ---
    def enroll(self, student_id: int, subject_id: int) -> None:
        if not self.db.query_one("SELECT 1 AS x FROM Enrollment WHERE student_id=%s AND subject_id=%s",
                                 (student_id, subject_id)):
            self.db.execute("INSERT INTO Enrollment (student_id, subject_id) VALUES (%s, %s)",
                            (student_id, subject_id))

    def unenroll(self, student_id: int, subject_id: int) -> None:
        self.db.execute("DELETE FROM Enrollment WHERE student_id=%s AND subject_id=%s", (student_id, subject_id))

    def subjects_for_student(self, student_id: int) -> list:
        rows = self.db.query(
            "SELECT s.* FROM Subject s JOIN Enrollment e ON e.subject_id = s.subject_id "
            "WHERE e.student_id = %s ORDER BY s.subject_name", (student_id,))
        return [Subject.from_row(r) for r in rows]

    def student_ids_for_subject(self, subject_id: int) -> list:
        return [r["student_id"] for r in self.db.query(
            "SELECT student_id FROM Enrollment WHERE subject_id = %s", (subject_id,))]


class SessionDAO(BaseDAO):
    def create(self, s: ClassSession) -> int:
        s.session_id = self.db.execute(
            "INSERT INTO ClassSession (subject_id, class_date, period) VALUES (%s, %s, %s)",
            (s.subject_id, s.class_date, s.period))
        return s.session_id

    def get(self, session_id: int):
        r = self.db.query_one("SELECT * FROM ClassSession WHERE session_id = %s", (session_id,))
        return ClassSession.from_row(r) if r else None

    def find(self, subject_id: int, class_date: str, period: int):
        r = self.db.query_one(
            "SELECT * FROM ClassSession WHERE subject_id=%s AND class_date=%s AND period=%s",
            (subject_id, class_date, period))
        return ClassSession.from_row(r) if r else None

    def list_for_subject(self, subject_id: int) -> list:
        rows = self.db.query("SELECT * FROM ClassSession WHERE subject_id=%s ORDER BY class_date, period", (subject_id,))
        return [ClassSession.from_row(r) for r in rows]

    def delete(self, session_id: int) -> None:
        self.db.execute("DELETE FROM ClassSession WHERE session_id = %s", (session_id,))


class AttendanceDAO(BaseDAO):
    def mark(self, rec: AttendanceRecord) -> int:
        """Insert or update one attendance row (a session/student pair is unique)."""
        existing = self.db.query_one(
            "SELECT attendance_id FROM Attendance WHERE session_id=%s AND student_id=%s",
            (rec.session_id, rec.student_id))
        ts = rec.marked_at or now_str()
        if existing:
            self.db.execute("UPDATE Attendance SET status=%s, marked_at=%s, marked_via=%s WHERE attendance_id=%s",
                            (rec.status, ts, rec.marked_via, existing["attendance_id"]))
            rec.attendance_id = existing["attendance_id"]
        else:
            rec.attendance_id = self.db.execute(
                "INSERT INTO Attendance (session_id, student_id, status, marked_at, marked_via) VALUES (%s,%s,%s,%s,%s)",
                (rec.session_id, rec.student_id, rec.status, ts, rec.marked_via))
        return rec.attendance_id

    def bulk_mark(self, session_id: int, marks: dict, via: str = "faculty") -> list:
        """marks = {student_id: 'P'|'A'|'OD'}. Returns the student_ids that were written."""
        for student_id, status in marks.items():
            self.mark(AttendanceRecord(session_id, int(student_id), status, marked_via=via))
        return [int(s) for s in marks]

    def delete(self, session_id: int, student_id: int) -> None:
        self.db.execute("DELETE FROM Attendance WHERE session_id=%s AND student_id=%s", (session_id, student_id))

    def roster(self, session_id: int) -> list:
        """Every enrolled student for the session's subject with their mark (None if not marked yet)."""
        return self.db.query(
            "SELECT st.student_id, st.reg_no, st.name, a.status "
            "FROM ClassSession cs "
            "JOIN Enrollment e ON e.subject_id = cs.subject_id "
            "JOIN Student st ON st.student_id = e.student_id "
            "LEFT JOIN Attendance a ON a.session_id = cs.session_id AND a.student_id = st.student_id "
            "WHERE cs.session_id = %s ORDER BY st.name", (session_id,))

    def summary_rows(self, student_id: int = None, subject_id: int = None) -> list:
        """Per student per subject: total classes, attended (P+OD), OD count. JOINs + GROUP BY."""
        where, params = [], []
        if student_id is not None:
            where.append("a.student_id = %s"); params.append(student_id)
        if subject_id is not None:
            where.append("cs.subject_id = %s"); params.append(subject_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return self.db.query(
            "SELECT st.student_id, st.reg_no, st.name AS student_name, "
            "       sub.subject_id, sub.subject_name, sub.subject_code, sub.planned_classes, "
            "       COUNT(*) AS total, "
            "       SUM(CASE WHEN a.status IN ('P','OD') THEN 1 ELSE 0 END) AS attended, "
            "       SUM(CASE WHEN a.status = 'OD' THEN 1 ELSE 0 END) AS od_count "
            "FROM Attendance a "
            "JOIN ClassSession cs ON a.session_id = cs.session_id "
            "JOIN Subject sub ON cs.subject_id = sub.subject_id "
            "JOIN Student st ON a.student_id = st.student_id "
            f"{clause} "
            "GROUP BY st.student_id, st.reg_no, st.name, sub.subject_id, sub.subject_name, "
            "         sub.subject_code, sub.planned_classes "
            "ORDER BY st.name, sub.subject_name", params)

    def history(self, student_id: int, subject_id: int) -> list:
        """Chronological list of statuses for one student in one subject."""
        return self.db.query(
            "SELECT cs.class_date, cs.period, a.status "
            "FROM Attendance a JOIN ClassSession cs ON a.session_id = cs.session_id "
            "WHERE a.student_id = %s AND cs.subject_id = %s ORDER BY cs.class_date, cs.period",
            (student_id, subject_id))

    def simultaneous_presence(self) -> list:
        """Students marked 'P' in two different subjects at the same date+period (impossible)."""
        return self.db.query(
            "SELECT a.student_id, cs.class_date, cs.period, COUNT(DISTINCT cs.subject_id) AS n "
            "FROM Attendance a JOIN ClassSession cs ON a.session_id = cs.session_id "
            "WHERE a.status = 'P' "
            "GROUP BY a.student_id, cs.class_date, cs.period HAVING COUNT(DISTINCT cs.subject_id) > 1")

    def session_marks(self) -> list:
        """Per session: how many marked and how many present (for anomaly detection)."""
        return self.db.query(
            "SELECT cs.session_id, cs.subject_id, cs.class_date, cs.period, COUNT(*) AS marked, "
            "       SUM(CASE WHEN a.status = 'P' THEN 1 ELSE 0 END) AS present "
            "FROM Attendance a JOIN ClassSession cs ON a.session_id = cs.session_id "
            "GROUP BY cs.session_id, cs.subject_id, cs.class_date, cs.period")


class TimetableDAO(BaseDAO):
    def set_slot(self, subject_id: int, day_of_week: int, period: int) -> None:
        self.db.execute("DELETE FROM Timetable WHERE day_of_week=%s AND period=%s", (day_of_week, period))
        self.db.execute("INSERT INTO Timetable (subject_id, day_of_week, period) VALUES (%s,%s,%s)",
                        (subject_id, day_of_week, period))

    def for_day(self, day_of_week: int) -> list:
        return self.db.query(
            "SELECT t.day_of_week, t.period, s.subject_id, s.subject_name, s.subject_code "
            "FROM Timetable t JOIN Subject s ON s.subject_id = t.subject_id "
            "WHERE t.day_of_week = %s ORDER BY t.period", (day_of_week,))

    def all_slots(self) -> list:
        return self.db.query(
            "SELECT t.day_of_week, t.period, s.subject_id, s.subject_name, s.subject_code "
            "FROM Timetable t JOIN Subject s ON s.subject_id = t.subject_id ORDER BY t.day_of_week, t.period")
