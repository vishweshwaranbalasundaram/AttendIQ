"""Report (abstract) -> AttendanceReport, ShortageReport, SubjectSummaryReport.

generate() is a Template Method; subclasses supply the title, columns and rows (polymorphism).
"""
from abc import ABC, abstractmethod

from attendiq.service.attendance_service import AttendanceService


class Report(ABC):
    def __init__(self):
        self.service = AttendanceService()

    @property
    @abstractmethod
    def title(self) -> str: ...

    @property
    @abstractmethod
    def columns(self) -> list: ...

    @abstractmethod
    def build_rows(self) -> list: ...

    def generate(self) -> dict:
        return {"title": self.title, "columns": self.columns, "rows": self.build_rows()}

    def render_text(self) -> str:
        data = self.generate()
        rows = [[str(c) for c in r] for r in data["rows"]]
        widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
                  for i, h in enumerate(data["columns"])]
        line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        fmt = lambda cells: "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"
        out = [data["title"], line, fmt(data["columns"]), line, *[fmt(r) for r in rows], line]
        return "\n".join(out)


class AttendanceReport(Report):
    """One student, every subject."""
    def __init__(self, student_id: int):
        super().__init__()
        self.student_id = student_id

    title = property(lambda self: f"Attendance report (student #{self.student_id})")
    columns = property(lambda self: ["Subject", "Attended", "Total", "%", "Status", "Need", "Safe skips"])

    def build_rows(self):
        return [[s["subject_name"], s["attended"], s["total"], s["percentage"], s["status"],
                 s["classes_needed"], s["safe_bunks"]] for s in self.service.stats(student_id=self.student_id)]


class ShortageReport(Report):
    """Everyone below the threshold (optionally one subject)."""
    def __init__(self, subject_id: int = None):
        super().__init__()
        self.subject_id = subject_id

    title = property(lambda self: "Shortage report")
    columns = property(lambda self: ["Reg No", "Student", "Subject", "%", "Need to recover"])

    def build_rows(self):
        rows = [s for s in self.service.stats(subject_id=self.subject_id) if s["status"] == "Shortage"]
        rows.sort(key=lambda s: s["percentage"])
        return [[s["reg_no"], s["student_name"], s["subject_name"], s["percentage"], s["classes_needed"]]
                for s in rows]


class SubjectSummaryReport(Report):
    """Per subject: class average and counts by status."""
    title = property(lambda self: "Subject-wise summary")
    columns = property(lambda self: ["Subject", "Students", "Average %", "Safe", "Warning", "Shortage"])

    def build_rows(self):
        agg = {}
        for s in self.service.stats():
            a = agg.setdefault(s["subject_name"], {"n": 0, "sum": 0.0, "Safe": 0, "Warning": 0, "Shortage": 0})
            a["n"] += 1
            a["sum"] += s["percentage"]
            a[s["status"]] = a.get(s["status"], 0) + 1
        return [[name, a["n"], round(a["sum"] / a["n"], 2), a["Safe"], a["Warning"], a["Shortage"]]
                for name, a in sorted(agg.items())]
