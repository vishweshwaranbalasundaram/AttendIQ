CREATE TABLE IF NOT EXISTS Student (
  student_id INT PRIMARY KEY AUTO_INCREMENT,
  reg_no VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(100) NOT NULL,
  department VARCHAR(50),
  year INT,
  email VARCHAR(100),
  telegram_chat_id VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS Faculty (
  faculty_id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  department VARCHAR(50),
  email VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Subject (
  subject_id INT PRIMARY KEY AUTO_INCREMENT,
  subject_code VARCHAR(20) UNIQUE,
  subject_name VARCHAR(100) NOT NULL,
  faculty_id INT NULL,
  planned_classes INT NOT NULL DEFAULT 60,
  FOREIGN KEY (faculty_id) REFERENCES Faculty(faculty_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Enrollment (
  student_id INT,
  subject_id INT,
  PRIMARY KEY (student_id, subject_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ClassSession (
  session_id INT PRIMARY KEY AUTO_INCREMENT,
  subject_id INT NOT NULL,
  class_date DATE NOT NULL,
  period INT NOT NULL,
  UNIQUE (subject_id, class_date, period),
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Attendance (
  attendance_id INT PRIMARY KEY AUTO_INCREMENT,
  session_id INT NOT NULL,
  student_id INT NOT NULL,
  status ENUM('P','A','OD') NOT NULL,
  marked_at DATETIME NULL,
  marked_via VARCHAR(20) NOT NULL DEFAULT 'faculty',
  UNIQUE (session_id, student_id),
  FOREIGN KEY (session_id) REFERENCES ClassSession(session_id) ON DELETE CASCADE,
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Timetable (
  slot_id INT PRIMARY KEY AUTO_INCREMENT,
  subject_id INT NOT NULL,
  day_of_week INT NOT NULL,
  period INT NOT NULL,
  UNIQUE (day_of_week, period),
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AppUser (
  user_id INT PRIMARY KEY AUTO_INCREMENT,
  role ENUM('student','faculty','admin') NOT NULL,
  username VARCHAR(50) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  linked_id INT NULL
);

CREATE TABLE IF NOT EXISTS Notification (
  notif_id INT PRIMARY KEY AUTO_INCREMENT,
  student_id INT NOT NULL,
  audience VARCHAR(10) NOT NULL DEFAULT 'student',
  message TEXT NOT NULL,
  channel VARCHAR(20) NOT NULL,
  sent_at DATETIME NOT NULL,
  status VARCHAR(20) NOT NULL,
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS RiskPrediction (
  pred_id INT PRIMARY KEY AUTO_INCREMENT,
  student_id INT NOT NULL,
  subject_id INT NOT NULL,
  predicted_percent DOUBLE NOT NULL,
  risk_level VARCHAR(20) NOT NULL,
  generated_at DATETIME NOT NULL,
  UNIQUE (student_id, subject_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS RecoveryPlan (
  plan_id INT PRIMARY KEY AUTO_INCREMENT,
  student_id INT NOT NULL,
  subject_id INT NOT NULL,
  classes_needed INT NOT NULL,
  plan_text TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
  FOREIGN KEY (subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AgentLog (
  log_id INT PRIMARY KEY AUTO_INCREMENT,
  agent_name VARCHAR(50) NOT NULL,
  action VARCHAR(100) NOT NULL,
  input_text TEXT,
  output_text TEXT,
  created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS QRToken (
  token_id INT PRIMARY KEY AUTO_INCREMENT,
  session_id INT NOT NULL,
  token VARCHAR(64) UNIQUE NOT NULL,
  expires_at DATETIME NOT NULL,
  FOREIGN KEY (session_id) REFERENCES ClassSession(session_id) ON DELETE CASCADE
);
