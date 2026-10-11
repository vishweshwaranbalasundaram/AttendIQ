"""Subject, ClassSession, AttendanceRecord."""
VALID_STATUS = ("P", "A", "OD")


class Subject:
    def __init__(self, subject_name, subject_code=None, faculty_id=None,
                 planned_classes=60, subject_id=None):
        if not subject_name:
            raise ValueError("subject_name cannot be empty")
        if int(planned_classes) <= 0:
            raise ValueError("planned_classes must be positive")
        self.subject_name = subject_name
        self.subject_code = subject_code
        self.faculty_id = faculty_id
        self.planned_classes = int(planned_classes)
        self.subject_id = subject_id

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_row(cls, r):
        return cls(r["subject_name"], r.get("subject_code"), r.get("faculty_id"),
                   r.get("planned_classes", 60), r.get("subject_id"))


class ClassSession:
    def __init__(self, subject_id, class_date, period, session_id=None):
        self.subject_id = subject_id
        self.class_date = str(class_date)
        self.period = int(period)
        self.session_id = session_id

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_row(cls, r):
        return cls(r["subject_id"], r["class_date"], r["period"], r.get("session_id"))


class AttendanceRecord:
    def __init__(self, session_id, student_id, status, marked_via="faculty",
                 marked_at=None, attendance_id=None):
        if status not in VALID_STATUS:
            raise ValueError(f"status must be one of {VALID_STATUS}")
        self.session_id = session_id
        self.student_id = student_id
        self.status = status
        self.marked_via = marked_via
        self.marked_at = marked_at
        self.attendance_id = attendance_id

    @property
    def counts_as_present(self) -> bool:
        return self.status in ("P", "OD")   # OD (on duty) counts as present

    def to_dict(self):
        return dict(self.__dict__)
