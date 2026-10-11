PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Student (
  student_id INTEGER PRIMARY KEY AUTOINCREMENT,
  reg_no TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  department TEXT,
  year INTEGER,
  email TEXT,
  telegram_chat_id TEXT
);

CREATE TABLE IF NOT EXISTS Faculty (
  faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  department TEXT,
  email TEXT
);

CREATE TABLE IF NOT EXISTS Subject (
  subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_code TEXT UNIQUE,
  subject_name TEXT NOT NULL,
  faculty_id INTEGER,
  planned_classes INTEGER NOT NULL DEFAULT 60,
  FOREIGN KEY (faculty_id) REFERENCES Faculty(faculty_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Enrollment (
  student_id INTEGER,
  subject_id INTEGER,
  PRIMARY KEY (student_id, subject_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ClassSession (
  session_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id INTEGER NOT NULL,
  class_date TEXT NOT NULL,
  period INTEGER NOT NULL,
  UNIQUE (subject_id, class_date, period),
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Attendance (
  attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  student_id INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('P','A','OD')),
  marked_at TEXT,
  marked_via TEXT NOT NULL DEFAULT 'faculty',
  UNIQUE (session_id, student_id),
  FOREIGN KEY (session_id) REFERENCES ClassSession(session_id) ON DELETE CASCADE,
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Timetable (
  slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id INTEGER NOT NULL,
  day_of_week INTEGER NOT NULL,   -- 0 = Monday ... 6 = Sunday
  period INTEGER NOT NULL,
  UNIQUE (day_of_week, period),
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AppUser (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  role TEXT NOT NULL CHECK (role IN ('student','faculty','admin')),
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  linked_id INTEGER
);

CREATE TABLE IF NOT EXISTS Notification (
  notif_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  audience TEXT NOT NULL DEFAULT 'student',
  message TEXT NOT NULL,
  channel TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  status TEXT NOT NULL,
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS RiskPrediction (
  pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  predicted_percent REAL NOT NULL,
  risk_level TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  UNIQUE (student_id, subject_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS RecoveryPlan (
  plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  classes_needed INTEGER NOT NULL,
  plan_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AgentLog (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_name TEXT NOT NULL,
  action TEXT NOT NULL,
  input_text TEXT,
  output_text TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS QRToken (
  token_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  token TEXT UNIQUE NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES ClassSession(session_id) ON DELETE CASCADE
);
