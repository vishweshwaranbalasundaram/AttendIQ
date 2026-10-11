"""AttendanceService: joins database rows with calculator results."""
from attendiq.dao import AttendanceDAO
from attendiq.service.calculator import AttendanceCalculator


class AttendanceService:
    def __init__(self, calculator: AttendanceCalculator = None):
        self.calc = calculator or AttendanceCalculator()
        self.attendance = AttendanceDAO()

    def stats(self, student_id: int = None, subject_id: int = None, student_ids: list = None) -> list:
        """One dict per (student, subject) with percentage, status, classes_needed, safe_bunks."""
        if student_ids is not None:
            rows = []
            for sid in student_ids:
                rows += self.attendance.summary_rows(student_id=sid, subject_id=subject_id)
        else:
            rows = self.attendance.summary_rows(student_id=student_id, subject_id=subject_id)
        out = []
        for r in rows:
            item = dict(r)
            item.update(self.calc.summarize(int(r["attended"]), int(r["total"])))
            item["remaining"] = max(0, int(r["planned_classes"]) - int(r["total"]))
            out.append(item)
        return out
