"""DAOs for the AI layer: notifications, predictions, recovery plans, agent audit log, QR tokens."""
from attendiq.dao.base import BaseDAO
from attendiq.util.db import now_str


class NotificationDAO(BaseDAO):
    def add(self, student_id, message, channel, status, audience="student") -> int:
        return self.db.execute(
            "INSERT INTO Notification (student_id, audience, message, channel, sent_at, status) "
            "VALUES (%s,%s,%s,%s,%s,%s)", (student_id, audience, message, channel, now_str(), status))

    def sent_today(self, student_id, audience, message) -> bool:
        day_start = now_str()[:10] + " 00:00:00"
        return self.db.query_one(
            "SELECT 1 AS x FROM Notification WHERE student_id=%s AND audience=%s AND message=%s AND sent_at >= %s",
            (student_id, audience, message, day_start)) is not None

    def list(self, student_id=None, audience=None, limit=100) -> list:
        where, params = [], []
        if student_id is not None:
            where.append("n.student_id = %s"); params.append(student_id)
        if audience is not None:
            where.append("n.audience = %s"); params.append(audience)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(int(limit))
        return self.db.query(
            "SELECT n.*, s.name AS student_name FROM Notification n JOIN Student s ON s.student_id = n.student_id "
            f"{clause} ORDER BY n.notif_id DESC LIMIT %s", params)


class RiskDAO(BaseDAO):
    def upsert(self, student_id, subject_id, predicted_percent, risk_level) -> None:
        self.db.execute("DELETE FROM RiskPrediction WHERE student_id=%s AND subject_id=%s", (student_id, subject_id))
        self.db.execute(
            "INSERT INTO RiskPrediction (student_id, subject_id, predicted_percent, risk_level, generated_at) "
            "VALUES (%s,%s,%s,%s,%s)", (student_id, subject_id, round(predicted_percent, 2), risk_level, now_str()))

    def list(self, student_id=None, min_level=None) -> list:
        where, params = [], []
        if student_id is not None:
            where.append("r.student_id = %s"); params.append(student_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = self.db.query(
            "SELECT r.*, st.name AS student_name, st.reg_no, sub.subject_name "
            "FROM RiskPrediction r JOIN Student st ON st.student_id = r.student_id "
            "JOIN Subject sub ON sub.subject_id = r.subject_id "
            f"{clause} ORDER BY r.predicted_percent ASC", params)
        return rows


class PlanDAO(BaseDAO):
    def replace(self, student_id, subject_id, classes_needed, plan_text) -> None:
        self.db.execute("DELETE FROM RecoveryPlan WHERE student_id=%s AND subject_id=%s", (student_id, subject_id))
        self.db.execute(
            "INSERT INTO RecoveryPlan (student_id, subject_id, classes_needed, plan_text, created_at) "
            "VALUES (%s,%s,%s,%s,%s)", (student_id, subject_id, classes_needed, plan_text, now_str()))

    def clear(self, student_id, subject_id) -> None:
        self.db.execute("DELETE FROM RecoveryPlan WHERE student_id=%s AND subject_id=%s", (student_id, subject_id))

    def list(self, student_id=None) -> list:
        where, params = "", []
        if student_id is not None:
            where, params = "WHERE p.student_id = %s", [student_id]
        return self.db.query(
            "SELECT p.*, st.name AS student_name, sub.subject_name "
            "FROM RecoveryPlan p JOIN Student st ON st.student_id = p.student_id "
            f"JOIN Subject sub ON sub.subject_id = p.subject_id {where} ORDER BY p.classes_needed DESC", params)


class AgentLogDAO(BaseDAO):
    def add(self, agent_name, action, input_text="", output_text="") -> int:
        return self.db.execute(
            "INSERT INTO AgentLog (agent_name, action, input_text, output_text, created_at) VALUES (%s,%s,%s,%s,%s)",
            (agent_name, action, str(input_text)[:2000], str(output_text)[:4000], now_str()))

    def recent(self, limit=50, agent_name=None) -> list:
        if agent_name:
            return self.db.query("SELECT * FROM AgentLog WHERE agent_name=%s ORDER BY log_id DESC LIMIT %s",
                                 (agent_name, int(limit)))
        return self.db.query("SELECT * FROM AgentLog ORDER BY log_id DESC LIMIT %s", (int(limit),))


class QRTokenDAO(BaseDAO):
    def create(self, session_id: int, token: str, expires_at: str) -> int:
        self.db.execute("DELETE FROM QRToken WHERE session_id = %s", (session_id,))  # one live token per session
        return self.db.execute("INSERT INTO QRToken (session_id, token, expires_at) VALUES (%s,%s,%s)",
                               (session_id, token, expires_at))

    def get_valid(self, token: str):
        return self.db.query_one("SELECT * FROM QRToken WHERE token = %s AND expires_at >= %s", (token, now_str()))
