"""StudentDAO, FacultyDAO, UserDAO."""
import hashlib
import hmac
import os

from attendiq import config
from attendiq.dao.base import BaseDAO
from attendiq.model import Student, Faculty


class StudentDAO(BaseDAO):
    def create(self, s: Student) -> int:
        s.student_id = self.db.execute(
            "INSERT INTO Student (reg_no, name, department, year, email, telegram_chat_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (s.reg_no, s.name, s.department, s.year, s.email, s.telegram_chat_id))
        return s.student_id

    def get(self, student_id: int):
        r = self.db.query_one("SELECT * FROM Student WHERE student_id = %s", (student_id,))
        return Student.from_row(r) if r else None

    def get_by_reg(self, reg_no: str):
        r = self.db.query_one("SELECT * FROM Student WHERE UPPER(reg_no) = UPPER(%s)", (reg_no,))
        return Student.from_row(r) if r else None

    def find(self, text: str) -> list:
        like = f"%{text}%"
        rows = self.db.query("SELECT * FROM Student WHERE name LIKE %s OR reg_no LIKE %s ORDER BY name", (like, like))
        return [Student.from_row(r) for r in rows]

    def list_all(self) -> list:
        return [Student.from_row(r) for r in self.db.query("SELECT * FROM Student ORDER BY name")]

    def update(self, s: Student) -> None:
        self.db.execute(
            "UPDATE Student SET name=%s, department=%s, year=%s, email=%s, telegram_chat_id=%s WHERE student_id=%s",
            (s.name, s.department, s.year, s.email, s.telegram_chat_id, s.student_id))

    def delete(self, student_id: int) -> None:
        self.db.execute("DELETE FROM Student WHERE student_id = %s", (student_id,))


class FacultyDAO(BaseDAO):
    def create(self, f: Faculty) -> int:
        f.faculty_id = self.db.execute(
            "INSERT INTO Faculty (name, department, email) VALUES (%s, %s, %s)",
            (f.name, f.department, f.email))
        return f.faculty_id

    def get(self, faculty_id: int):
        r = self.db.query_one("SELECT * FROM Faculty WHERE faculty_id = %s", (faculty_id,))
        return Faculty.from_row(r) if r else None

    def list_all(self) -> list:
        return [Faculty.from_row(r) for r in self.db.query("SELECT * FROM Faculty ORDER BY name")]

    def update(self, f: Faculty) -> None:
        self.db.execute("UPDATE Faculty SET name=%s, department=%s, email=%s WHERE faculty_id=%s",
                        (f.name, f.department, f.email, f.faculty_id))

    def delete(self, faculty_id: int) -> None:
        self.db.execute("DELETE FROM Faculty WHERE faculty_id = %s", (faculty_id,))


class UserDAO(BaseDAO):
    """Login accounts. Passwords are stored as salted PBKDF2 hashes, never plain text."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Format: iterations$salt$hash (all hex), so the cost can change without breaking old hashes."""
        iters = config.PBKDF2_ITERATIONS
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iters)
        return f"{iters}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, stored: str) -> bool:
        try:
            iters, salt_hex, digest_hex = stored.split("$")
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
            return hmac.compare_digest(digest.hex(), digest_hex)
        except ValueError:
            return False

    def create(self, username: str, password: str, role: str, linked_id: int = None) -> int:
        return self.db.execute(
            "INSERT INTO AppUser (role, username, password_hash, linked_id) VALUES (%s, %s, %s, %s)",
            (role, username, self.hash_password(password), linked_id))

    def get_by_username(self, username: str):
        return self.db.query_one("SELECT * FROM AppUser WHERE username = %s", (username,))

    def authenticate(self, username: str, password: str):
        u = self.get_by_username(username)
        if u and self.verify_password(password, u["password_hash"]):
            return u
        return None
