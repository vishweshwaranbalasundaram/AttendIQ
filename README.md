# AttendIQ — Agentic AI Attendance Monitoring, Prediction and Recovery Planning

OOPs + DBMS semester project. Python, SQL (SQLite or MySQL), FastAPI, Streamlit.

## 1. Run it (5 minutes)

```bash
pip install -r requirements.txt

python -m attendiq.seed          # creates tables + demo data (4 faculty, 5 subjects, 12 students, 150 classes)

# Option A: console menu app (no server needed, great for the viva)
python -m attendiq.cli

# Option B: API + dashboard (two terminals)
uvicorn attendiq.api.app:app --reload          # API docs at http://127.0.0.1:8000/docs
streamlit run ui/dashboard.py                  # dashboard at http://localhost:8501
```

**Demo logins (demo only, change before any real use):**
`admin / admin123` · `f1 … f4 / faculty123` · students: reg no in lowercase, e.g. `rec24cs001 / student123`
(`rec24cs012` is a heavy-shortage student, good for demos; `rec24cs001` is safe.)

### Use MySQL instead of SQLite
```sql
CREATE DATABASE attendance_tracker;
```
Copy `.env.example` to `.env`, set `ATTENDIQ_DB=mysql` and the `MYSQL_*` values, then run `python -m attendiq.seed` again.
The full schema for MySQL is in `db/schema_mysql.sql` (SQLite version: `db/schema_sqlite.sql`).

### Turn on the real AI assistant
Set `ANTHROPIC_API_KEY` (and optionally `ATTENDIQ_MODEL`) in `.env`. Without a key the ChatAgent runs in an offline
rule-based mode that calls the very same tools, so the demo always works.

### Tests
```bash
pytest                                   # 39 tests, in-memory SQLite, ~2 s
ATTENDIQ_TEST_DB=mysql pytest            # same tests against a real MySQL/MariaDB (uses MYSQL_* env vars)
```

## 2. Architecture

```
 Streamlit dashboard / Console menu
              |
        FastAPI (JWT + roles)
              |
   AgentOrchestrator:  Monitor -> Predictor -> Planner -> Anomaly -> Notifier      ChatAgent (LLM + tools)
              |                                                                          |
   Service layer: AttendanceCalculator, AttendanceService, Reports          Tools = read-only DAO wrappers
              |
   DAO layer (all SQL lives here)  ->  DBConnection (Singleton)  ->  SQLite / MySQL
```

```
attendiq/
  model/     Person, Student, Faculty, Subject, ClassSession, AttendanceRecord
  dao/       StudentDAO, FacultyDAO, UserDAO, SubjectDAO, SessionDAO, AttendanceDAO, TimetableDAO,
             NotificationDAO, RiskDAO, PlanDAO, AgentLogDAO, QRTokenDAO
  service/   AttendanceCalculator (the maths), AttendanceService
  agents/    Agent (abstract), Monitor, Predictor, Planner, Anomaly, Notifier, Chat, Orchestrator
  report/    Report (abstract), AttendanceReport, ShortageReport, SubjectSummaryReport
  api/       app.py (REST), auth.py (JWT, roles)
  util/db.py DBConnection singleton
  cli.py     console menu     seed.py  demo data     config.py  settings
ui/dashboard.py   db/*.sql   tests/
```

## 3. Where each syllabus concept lives (for the viva)

| Concept | Where |
|---|---|
| Classes and objects | `model/*`, every DAO, agent and report |
| Inheritance | `Person -> Student/Faculty`; `Agent -> 6 agents`; `Report -> 3 reports` |
| Abstraction | abstract `Agent` (`run`) and `Report` (`title`, `columns`, `build_rows`) |
| Polymorphism | every agent overrides `run()`; every report overrides `build_rows()`; `Person.role()` |
| Encapsulation | private fields with validating properties (`Student.year`, `Person.email`) |
| Singleton | `DBConnection` |
| Template Method | `Agent.execute()` (logging + error containment), `Report.generate()` |
| DAO pattern | all SQL is inside `dao/` |
| Database design | 6 core + 7 extension tables, 3NF, PK/FK, composite PK, UNIQUE, CHECK/ENUM, ON DELETE CASCADE |
| Joins / aggregation | `AttendanceDAO.summary_rows` (4-table JOIN, GROUP BY, SUM(CASE...)), `roster` (LEFT JOIN), anomaly queries (HAVING) |
| CRUD | Students, Faculty, Subjects, Enrollment, Sessions, Attendance (insert/update/delete) |
| DB connectivity | `util/db.py` (sqlite3 / mysql-connector, parameterised queries only) |

## 4. The attendance maths

For attended `a`, total `t`, threshold `T` (default 75): percentage = a/t·100; classes needed to recover =
`ceil((T·t − 100a)/(100 − T))` (= `3t − 4a` at 75%); safe skips = `floor(100a/T − t)`. OD counts as present.
Fractions are used internally so there are no rounding errors; exactly 75.00% is not a shortage.

## 5. What the agents do (and do not do)

| Agent | Behaviour |
|---|---|
| MonitorAgent | recomputes stats, flags Safe / Warning / Shortage |
| PredictorAgent | projects end-of-semester % = attended + (0.6·recent rate + 0.4·overall rate)·remaining classes; risk Low/Medium/High/Critical (Critical = cannot reach 75% even with perfect attendance) |
| PlannerAgent | writes a recovery plan per subject and lists subjects where the student can still afford to miss |
| AnomalyAgent | rule-based: present in two subjects at the same period, 100%-present large sessions, high OD share |
| NotifierAgent | alerts students (Telegram, email or stored as `simulated`), de-duplicates per day, escalates to faculty |
| ChatAgent | natural-language Q&A through 5 read-only tools |

Agents run automatically whenever faculty save attendance (`PUT /sessions/{id}/attendance`) or a student scans a QR.

**Safety rules built into the code:** agents never change attendance marks (tested); the chat tools are read-only; a student
is always pinned to their own data on the server side; the LLM cannot write SQL (only the 5 tools exist); every agent action
goes to `AgentLog`; a crashing agent is contained and logged instead of breaking attendance marking; passwords are salted PBKDF2
hashes; faculty can only mark subjects they teach.

## 6. Known limits (say these honestly in the viva, it earns marks)

* The predictor is a transparent heuristic, not a trained ML model.
* The LLM path is verified with a fake client in tests; the live Claude call needs your API key. Telegram/email sending needs
  your own credentials and was not exercised against the real services. Without them alerts are stored as `simulated`.
* QR codes expire after 90 seconds, but a screenshot can still be forwarded to a friend. There is no geofencing.
* Demo passwords and the default `ATTENDIQ_SECRET` are for development only.

## 7. Suggested demo flow

1. Show `db/schema_mysql.sql` / the ER structure. 2. `python -m attendiq.cli` -> report 8 (shortage).
3. Log in as `f1`, mark attendance for DBMS, show the agents' summary appear. 4. Log in as `rec24cs012`: recovery plan,
prediction, alert. 5. Ask the chat "Can I skip DMS tomorrow?" and "What if I miss 3 classes in OS?". 6. Show `AgentLog`.
7. Update and delete a student to prove CRUD (CLI options 3 and 4).
