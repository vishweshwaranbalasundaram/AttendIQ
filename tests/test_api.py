import pytest
from fastapi.testclient import TestClient

from attendiq.api.app import app
from attendiq.dao import SessionDAO, StudentDAO


@pytest.fixture
def client():
    return TestClient(app)


def login(client, user, pw):
    r = client.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_login_and_auth_required(client):
    assert client.get("/students").status_code == 401
    assert client.post("/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    h = login(client, "admin", "admin123")
    assert client.get("/me", headers=h).json()["role"] == "admin"
    assert client.get("/students", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_admin_student_crud(client):
    h = login(client, "admin", "admin123")
    r = client.post("/students", json={"name": "Api Kid", "reg_no": "API001", "department": "CSE", "year": 2}, headers=h)
    assert r.status_code == 201
    sid = r.json()["student_id"]
    assert client.post("/students", json={"name": "Dup", "reg_no": "API001"}, headers=h).status_code == 409
    assert client.post("/students", json={"name": "Bad", "reg_no": "B1", "year": 9}, headers=h).status_code == 400
    assert client.put(f"/students/{sid}", json={"name": "Api Renamed", "reg_no": "API001", "year": 2}, headers=h).json()["name"] == "Api Renamed"
    assert client.delete(f"/students/{sid}", headers=h).status_code == 204
    assert client.get(f"/students/{sid}", headers=h).status_code == 404


def test_student_is_pinned_to_own_data(client):
    h = login(client, "rec24cs001", "student123")
    other = StudentDAO().get_by_reg("REC24CS012").student_id
    me = client.get("/me", headers=h).json()["linked_id"]
    rows = client.get(f"/attendance/summary?student_id={other}", headers=h).json()
    assert rows and all(r["student_id"] == me for r in rows)
    assert client.get(f"/students/{other}", headers=h).status_code == 403
    assert client.get("/students", headers=h).status_code == 403
    assert client.post("/students", json={"name": "x", "reg_no": "y"}, headers=h).status_code == 403
    assert client.get("/reports/shortage", headers=h).status_code == 403
    assert client.post("/agents/run", headers=h).status_code == 403


def test_faculty_marks_attendance_and_agents_react(client):
    h = login(client, "f1", "faculty123")                   # f1 teaches DBMS (subject 1)
    r = client.post("/sessions", json={"subject_id": 1, "class_date": "2026-09-14", "period": 1}, headers=h)
    assert r.status_code == 201
    sid = r.json()["session_id"]
    roster = r.json()["roster"]
    assert len(roster) == 12
    marks = {str(x["student_id"]): "A" for x in roster}
    out = client.put(f"/sessions/{sid}/attendance", json={"marks": marks}, headers=h)
    assert out.status_code == 200 and out.json()["marked"] == 12
    assert out.json()["agents"]["MonitorAgent"]["checked"] > 0
    assert client.put(f"/sessions/{sid}/attendance", json={"marks": {"1": "LATE"}}, headers=h).status_code == 400
    assert client.put(f"/sessions/{sid}/attendance", json={"marks": {"999": "P"}}, headers=h).status_code == 400
    # edit a mistake
    assert client.put(f"/sessions/{sid}/attendance", json={"marks": {"1": "P"}}, headers=h).status_code == 200
    assert client.delete(f"/sessions/{sid}/attendance/1", headers=h).status_code == 204


def test_faculty_cannot_touch_other_facultys_subject(client):
    h = login(client, "f2", "faculty123")                   # f2 teaches OOPS and CN, not DBMS
    r = client.post("/sessions", json={"subject_id": 1, "class_date": "2026-09-14", "period": 1}, headers=h)
    assert r.status_code == 403
    assert client.post("/sessions", json={"subject_id": 2, "class_date": "not-a-date", "period": 1}, headers=h).status_code == 400


def test_reports_agents_and_chat_over_api(client):
    f = login(client, "f1", "faculty123")
    assert client.get("/reports/shortage", headers=f).json()["rows"]
    assert len(client.get("/reports/subject-summary", headers=f).json()["rows"]) == 5
    assert client.post("/agents/run", headers=f).json()["MonitorAgent"]["shortage"] > 0
    assert client.get("/agents/log", headers=f).json()
    assert client.get("/notifications", headers=f).json()
    s = login(client, "rec24cs012", "student123")
    assert client.get("/plans", headers=s).json()
    assert client.get("/predictions", headers=s).json()
    chat = client.post("/chat", json={"message": "how many classes do I need in DBMS?"}, headers=s).json()
    assert chat["tool_calls"][0]["tool"] == "get_attendance" and "Database Management Systems" in chat["reply"]
    assert client.post("/chat", json={"message": "  "}, headers=s).status_code == 400


def test_qr_attendance_flow(client):
    f = login(client, "f1", "faculty123")
    sid = client.post("/sessions", json={"subject_id": 1, "class_date": "2026-09-15", "period": 2}, headers=f).json()["session_id"]
    qr = client.post(f"/sessions/{sid}/qr", headers=f).json()
    s = login(client, "rec24cs012", "student123")
    assert client.post("/attendance/qr-scan", json={"token": "bogus"}, headers=s).status_code == 400
    ok = client.post("/attendance/qr-scan", json={"token": qr["payload"]}, headers=s)
    assert ok.status_code == 200 and ok.json()["marked"] == "P"
    roster = client.get(f"/sessions/{sid}/roster", headers=f).json()
    me = [r for r in roster if r["reg_no"] == "REC24CS012"][0]
    assert me["status"] == "P"
    assert client.post("/attendance/qr-scan", json={"token": qr["payload"]}, headers=f).status_code == 403   # faculty cannot scan


def test_expired_qr_rejected(client):
    from attendiq.dao import QRTokenDAO
    f = login(client, "f1", "faculty123")
    sid = client.post("/sessions", json={"subject_id": 1, "class_date": "2026-09-16", "period": 3}, headers=f).json()["session_id"]
    QRTokenDAO().create(sid, "oldtoken", "2000-01-01 00:00:00")
    s = login(client, "rec24cs001", "student123")
    assert client.post("/attendance/qr-scan", json={"token": "oldtoken"}, headers=s).status_code == 400
