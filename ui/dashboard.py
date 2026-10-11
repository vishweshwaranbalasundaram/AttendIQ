"""Streamlit dashboard. Start the API first, then:  streamlit run ui/dashboard.py"""
import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("ATTENDIQ_API", "http://127.0.0.1:8000")
st.set_page_config(page_title="AttendIQ", page_icon="🎯", layout="wide")


def call(method, path, **kw):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.get("token") else {}
    try:
        r = requests.request(method, f"{API}{path}", headers=headers, timeout=30, **kw)
    except requests.ConnectionError:
        st.error(f"Cannot reach the API at {API}. Start it with: uvicorn attendiq.api.app:app")
        st.stop()
    if r.status_code == 401 and st.session_state.get("token"):
        st.session_state.clear()
        st.rerun()
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        return None, detail
    return (r.json() if r.content else {}), None


def status_icon(s):
    return {"Safe": "🟢", "Warning": "🟡", "Shortage": "🔴"}.get(s, "⚪")


# ---------------- login ----------------
def login_page():
    st.title("🎯 AttendIQ")
    st.caption("Agentic AI attendance monitoring, prediction and recovery planning")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            data, err = call("POST", "/auth/login", json={"username": u, "password": p})
            if err:
                st.error(err)
            else:
                st.session_state.update(token=data["access_token"], role=data["role"], linked_id=data["linked_id"], user=u)
                st.rerun()
    st.info("Demo accounts: admin/admin123 · f1/faculty123 · rec24cs001/student123")


# ---------------- student pages ----------------
def student_home():
    rows, err = call("GET", "/attendance/summary")
    if err or not rows:
        st.warning(err or "No attendance recorded yet.")
        return
    st.subheader("My attendance")
    cols = st.columns(len(rows))
    for col, r in zip(cols, rows):
        col.metric(f"{status_icon(r['status'])} {r['subject_code'] or r['subject_name']}", f"{r['percentage']}%",
                   f"{r['attended']}/{r['total']}", delta_color="off")
    df = pd.DataFrame(rows)[["subject_name", "attended", "total", "percentage", "status", "classes_needed", "safe_bunks"]]
    st.bar_chart(df.set_index("subject_name")["percentage"])
    st.dataframe(df.rename(columns={"subject_name": "Subject", "classes_needed": "Need to recover",
                                    "safe_bunks": "Safe skips"}), width="stretch", hide_index=True)
    plans, _ = call("GET", "/plans")
    if plans:
        st.subheader("🧭 My recovery plan")
        for p in plans:
            st.info(p["plan_text"])
    preds, _ = call("GET", "/predictions")
    if preds:
        st.subheader("🔮 End-of-semester prediction")
        st.dataframe(pd.DataFrame(preds)[["subject_name", "predicted_percent", "risk_level"]], hide_index=True,
                     width="stretch")


def qr_scan_page():
    st.subheader("Scan attendance QR")
    st.caption("Type or paste the code shown on the faculty screen (valid for 90 seconds).")
    token = st.text_input("QR code text", placeholder="attendiq:abcd1234")
    if st.button("Mark me present") and token:
        data, err = call("POST", "/attendance/qr-scan", json={"token": token})
        st.error(err) if err else st.success("Marked present ✔")


def alerts_page():
    st.subheader("My alerts")
    notes, _ = call("GET", "/notifications")
    for n in notes or []:
        st.warning(f"{n['sent_at']} · {n['channel']} ({n['status']}): {n['message']}")
    if not notes:
        st.success("No alerts. Keep it up!")


def chat_page():
    st.subheader("💬 Ask AttendIQ")
    st.caption('Try: "Can I skip DMS tomorrow?" · "How many classes do I need in OS?" · "What if I miss 3 classes in CN?"')
    if "chat" not in st.session_state:
        st.session_state.chat = []
    for m in st.session_state.chat:
        st.chat_message(m["role"]).write(m["text"])
    q = st.chat_input("Ask about attendance")
    if q:
        st.session_state.chat.append({"role": "user", "text": q})
        data, err = call("POST", "/chat", json={"message": q})
        reply = err or f"{data['reply']}\n\n_mode: {data['mode']}_"
        st.session_state.chat.append({"role": "assistant", "text": reply})
        st.rerun()


# ---------------- faculty / admin pages ----------------
def overview_page():
    st.subheader("Class overview")
    summ, _ = call("GET", "/reports/subject-summary")
    if summ:
        df = pd.DataFrame(summ["rows"], columns=summ["columns"])
        st.dataframe(df, hide_index=True, width="stretch")
        st.bar_chart(df.set_index("Subject")["Average %"])
    st.subheader("🔴 Shortage list")
    short, _ = call("GET", "/reports/shortage")
    if short:
        st.dataframe(pd.DataFrame(short["rows"], columns=short["columns"]), hide_index=True, width="stretch")
    preds, _ = call("GET", "/predictions")
    if preds:
        crit = [p for p in preds if p["risk_level"] in ("Critical", "High")]
        st.subheader(f"🔮 High-risk predictions ({len(crit)})")
        if crit:
            st.dataframe(pd.DataFrame(crit)[["student_name", "reg_no", "subject_name", "predicted_percent", "risk_level"]],
                         hide_index=True, width="stretch")


def mark_page():
    st.subheader("Mark attendance")
    subjects, _ = call("GET", "/subjects")
    me, _ = call("GET", "/me")
    mine = [s for s in subjects if st.session_state.role == "admin" or s["faculty_id"] == st.session_state.linked_id]
    if not mine:
        st.info("You are not assigned to any subject.")
        return
    sub = st.selectbox("Subject", mine, format_func=lambda s: f"{s['subject_code']} - {s['subject_name']}")
    c1, c2 = st.columns(2)
    date = c1.date_input("Date")
    period = c2.number_input("Period", 1, 8, 1)
    if st.button("Open class session"):
        data, err = call("POST", "/sessions", json={"subject_id": sub["subject_id"], "class_date": str(date), "period": int(period)})
        if err and "Duplicate" in err:
            sessions_msg = "A session already exists for that date and period; enter its id below."
            st.info(sessions_msg)
        elif err:
            st.error(err)
        else:
            st.session_state.session = data
    s = st.session_state.get("session")
    sid = st.number_input("Session id", 1, value=s["session_id"] if s else 1)
    roster, err = call("GET", f"/sessions/{int(sid)}/roster")
    if err:
        st.caption(err)
        return
    df = pd.DataFrame(roster)
    df["status"] = df["status"].fillna("P")
    edited = st.data_editor(df, hide_index=True, width="stretch", disabled=["student_id", "reg_no", "name"],
                            column_config={"status": st.column_config.SelectboxColumn("Status", options=["P", "A", "OD"])})
    if st.button("Save attendance", type="primary"):
        marks = {int(r.student_id): r.status for r in edited.itertuples()}
        data, err = call("PUT", f"/sessions/{int(sid)}/attendance", json={"marks": marks})
        if err:
            st.error(err)
        else:
            st.success(f"Saved {data['marked']} marks. Agents ran automatically:")
            st.json({k: v for k, v in data["agents"].items() if k != "findings"})


def qr_page():
    st.subheader("QR attendance")
    sid = st.number_input("Session id", 1, value=1)
    if st.button("Generate QR (valid 90 s)"):
        data, err = call("POST", f"/sessions/{int(sid)}/qr")
        if err:
            st.error(err)
        else:
            st.code(data["payload"])
            try:
                import io, qrcode
                buf = io.BytesIO()
                qrcode.make(data["payload"]).save(buf, format="PNG")
                st.image(buf.getvalue(), width=260)
            except ImportError:
                st.caption("Install `qrcode` to draw the image: pip install qrcode[pil]")
            st.caption(f"Expires at {data['expires_at']} UTC. A shared screenshot can be forwarded to a friend, "
                       "so keep the window short and watch the Anomaly findings.")


def agents_page():
    st.subheader("🤖 Agents")
    for line in call("GET", "/agents")[0] or []:
        st.write("•", line)
    if st.button("Run all agents now", type="primary"):
        data, err = call("POST", "/agents/run")
        if err:
            st.error(err)
        else:
            st.json({k: v for k, v in data.items() if k != "findings"})
            for f in data.get("findings", []):
                (st.error if f["severity"] == "high" else st.warning)(f["detail"])
    st.subheader("Audit log")
    log, _ = call("GET", "/agents/log", params={"limit": 40})
    if log:
        st.dataframe(pd.DataFrame(log)[["created_at", "agent_name", "action", "output_text"]], hide_index=True,
                     width="stretch")


def faculty_alerts_page():
    st.subheader("Escalations and alerts")
    notes, _ = call("GET", "/notifications")
    esc = [n for n in notes or [] if n["audience"] == "faculty"]
    for n in esc:
        st.error(f"{n['sent_at']} · {n['message']}")
    if not esc:
        st.success("No escalations.")
    with st.expander("Messages sent to students"):
        st.dataframe(pd.DataFrame([n for n in notes or [] if n["audience"] == "student"]), hide_index=True)


# ---------------- router ----------------
if not st.session_state.get("token"):
    login_page()
else:
    role = st.session_state.role
    st.sidebar.title("🎯 AttendIQ")
    st.sidebar.caption(f"{st.session_state.user} · {role}")
    pages = ({"My attendance": student_home, "Ask AttendIQ": chat_page, "Scan QR": qr_scan_page, "My alerts": alerts_page}
             if role == "student" else
             {"Overview": overview_page, "Mark attendance": mark_page, "QR attendance": qr_page,
              "Agents": agents_page, "Alerts": faculty_alerts_page, "Ask AttendIQ": chat_page})
    choice = st.sidebar.radio("Go to", list(pages))
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()
    pages[choice]()
