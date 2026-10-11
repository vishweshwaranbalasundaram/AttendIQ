"""Person -> Student / Faculty. Demonstrates inheritance and encapsulation."""


class Person:
    """Base class: private fields exposed through validated properties."""

    def __init__(self, name: str, email: str = None, department: str = None):
        self.name = name
        self._email = None
        self.email = email
        self._department = department

    # --- encapsulation: validate on the way in ---
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if not value or not str(value).strip():
            raise ValueError("name cannot be empty")
        self._name = str(value).strip()

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value):
        if value and "@" not in value:
            raise ValueError(f"invalid email: {value}")
        self._email = value

    @property
    def department(self):
        return self._department

    @department.setter
    def department(self, value):
        self._department = value

    def role(self) -> str:  # overridden by subclasses (polymorphism)
        return "person"

    def to_dict(self) -> dict:
        return {"name": self.name, "email": self.email, "department": self.department, "role": self.role()}


class Student(Person):
    def __init__(self, name, reg_no, department=None, year=None, email=None,
                 student_id=None, telegram_chat_id=None):
        super().__init__(name, email, department)
        if not reg_no or not str(reg_no).strip():
            raise ValueError("reg_no cannot be empty")
        self._reg_no = str(reg_no).strip()
        self._year = None
        self.year = year               # goes through the validating setter
        self.student_id = student_id
        self.telegram_chat_id = telegram_chat_id

    @property
    def reg_no(self) -> str:
        return self._reg_no

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, value):
        if value is not None and not (1 <= int(value) <= 6):
            raise ValueError("year must be between 1 and 6")
        self._year = value

    def role(self) -> str:
        return "student"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update(student_id=self.student_id, reg_no=self.reg_no, year=self.year,
                 telegram_chat_id=self.telegram_chat_id)
        return d

    @classmethod
    def from_row(cls, r: dict) -> "Student":
        return cls(r["name"], r["reg_no"], r.get("department"), r.get("year"), r.get("email"),
                   r.get("student_id"), r.get("telegram_chat_id"))


class Faculty(Person):
    def __init__(self, name, department=None, email=None, faculty_id=None):
        super().__init__(name, email, department)
        self.faculty_id = faculty_id

    def role(self) -> str:
        return "faculty"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["faculty_id"] = self.faculty_id
        return d

    @classmethod
    def from_row(cls, r: dict) -> "Faculty":
        return cls(r["name"], r.get("department"), r.get("email"), r.get("faculty_id"))
