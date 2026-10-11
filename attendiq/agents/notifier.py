import json
import logging
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

from attendiq import config
from attendiq.agents.base import Agent
from attendiq.dao import NotificationDAO, StudentDAO

log = logging.getLogger("attendiq.notifier")


class NotifierAgent(Agent):
    """Turns alerts into notifications.

    Channels are tried in order: Telegram (token + chat id), email (SMTP + student email), otherwise the
    message is only stored with status 'simulated'. Repeats are suppressed (same message, same day).
    Escalation: students in shortage in 2+ subjects, or with a Critical prediction, are also reported
    to faculty (stored with audience='faculty', shown on the dashboard).
    """
    name = "NotifierAgent"
    purpose = "Sends alerts to students and escalates persistent risk to faculty."

    def __init__(self, calculator=None):
        super().__init__(calculator)
        self.notifs = NotificationDAO()
        self.students = StudentDAO()

    # ---- delivery ----
    def _send_telegram(self, chat_id: str, text: str) -> bool:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as resp:
            return json.loads(resp.read()).get("ok", False)

    def _send_email(self, to: str, text: str) -> bool:
        cfg = config.SMTP
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = "AttendIQ attendance alert", cfg["from"] or cfg["user"], to
        msg.set_content(text)
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as smtp:
            smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
        return True

    def _deliver(self, student, text: str):
        """Returns (channel, status)."""
        try:
            if config.TELEGRAM_BOT_TOKEN and student.telegram_chat_id:
                return "telegram", "sent" if self._send_telegram(student.telegram_chat_id, text) else "failed"
            if config.SMTP["host"] and student.email:
                return "email", "sent" if self._send_email(student.email, text) else "failed"
        except Exception as exc:
            log.warning("delivery failed for %s: %s", student.reg_no, exc)
            return "telegram" if config.TELEGRAM_BOT_TOKEN and student.telegram_chat_id else "email", "failed"
        log.info("[simulated alert to %s] %s", student.reg_no, text)
        return "console", "simulated"

    # ---- agent ----
    def run(self, context: dict) -> dict:
        alerts = context.get("alerts", [])
        predictions = {(p["student_id"], p["subject_id"]): p for p in context.get("predictions", [])}
        by_student = {}
        for a in alerts:
            by_student.setdefault(a["student_id"], []).append(a)

        sent = skipped = escalated = 0
        for student_id, rows in by_student.items():
            student = self.students.get(student_id)
            if not student:
                continue
            lines = []
            for r in sorted(rows, key=lambda x: x["percentage"]):
                if r["status"] == "Shortage":
                    lines.append(f"SHORTAGE in {r['subject_name']} ({r['percentage']}%): attend the next "
                                 f"{r['classes_needed']} classes.")
                else:
                    lines.append(f"Warning in {r['subject_name']} ({r['percentage']}%): "
                                 f"only {r['safe_bunks']} safe miss(es) left.")
            text = f"Hi {student.name.split()[0]}, " + " ".join(lines)
            if self.notifs.sent_today(student_id, "student", text):
                skipped += 1
            else:
                channel, status = self._deliver(student, text)
                self.notifs.add(student_id, text, channel, status, "student")
                sent += 1

            short = [r for r in rows if r["status"] == "Shortage"]
            critical = [r for r in short if predictions.get((student_id, r["subject_id"]), {}).get("risk_level") == "Critical"]
            if len(short) >= 2 or critical:
                why = ("cannot recover in " + ", ".join(r["subject_name"] for r in critical)) if critical \
                    else f"in shortage in {len(short)} subjects"
                ftext = f"ESCALATION: {student.name} ({student.reg_no}) is {why}. Please follow up."
                if not self.notifs.sent_today(student_id, "faculty", ftext):
                    self.notifs.add(student_id, ftext, "dashboard", "sent", "faculty")
                    escalated += 1
        return {"students_alerted": sent, "duplicates_skipped": skipped, "escalated_to_faculty": escalated}
