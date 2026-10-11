import json
from types import SimpleNamespace

from attendiq import config
from attendiq.agents import ChatAgent
from attendiq.dao import StudentDAO


def student_chat(reg="REC24CS012"):
    s = StudentDAO().get_by_reg(reg)
    return ChatAgent(role="student", linked_id=s.student_id), s


def test_offline_attendance_answer():
    agent, _ = student_chat()
    out = agent.chat("what is my attendance?")
    assert out["mode"] == "offline" and "Lakshmi Priya" in out["reply"] and "Database Management Systems" in out["reply"]


def test_offline_can_i_skip_uses_tool():
    agent, _ = student_chat()
    out = agent.chat("Can I skip DMS tomorrow?")
    assert out["tool_calls"][0]["tool"] == "can_i_skip"
    assert any(w in out["reply"] for w in ("skip", "scheduled"))


def test_offline_what_if_numbers():
    agent, s = student_chat()
    out = agent.chat("what if I miss 3 classes in OS")
    assert out["tool_calls"][0]["tool"] == "what_if" and out["tool_calls"][0]["input"]["miss"] == 3


def test_student_cannot_see_others_or_list_shortage():
    agent, me = student_chat("REC24CS001")
    other = StudentDAO().get_by_reg("REC24CS012")
    out = agent.tools.call("get_attendance", {"student": other.reg_no})
    assert out["reg_no"] == me.reg_no                       # forced to own data
    assert "error" in agent.tools.call("list_shortage", {})


def test_faculty_can_list_shortage_and_look_up_student():
    agent = ChatAgent(role="faculty", linked_id=1)
    assert agent.tools.call("list_shortage", {})["count"] > 0
    out = agent.chat("who is below 75%")
    assert "below" in out["reply"]
    out = agent.chat("attendance of REC24CS012 in DBMS")
    assert "Lakshmi Priya" in out["reply"]


def test_tools_reject_unknown_tool_and_bad_args():
    agent, _ = student_chat()
    assert "error" in agent.tools.call("drop_tables", {})
    assert "error" in agent.tools.call("get_attendance", {"nonsense": 1})


# ---- LLM tool-calling loop, tested with a fake client (no API key / network needed) ----
class FakeClient:
    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        if self.calls == 1:
            block = SimpleNamespace(type="tool_use", id="tu_1", name="get_attendance", input={"subject": "DBMS"})
            return SimpleNamespace(stop_reason="tool_use", content=[block])
        last = kw["messages"][-1]["content"][0]
        assert last["type"] == "tool_result" and "percentage" in last["content"]
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="You are at X%.")])


def test_llm_tool_loop_with_fake_client():
    s = StudentDAO().get_by_reg("REC24CS003")
    agent = ChatAgent(role="student", linked_id=s.student_id, client=FakeClient())
    out = agent.chat("How am I doing in DBMS?")
    assert out["mode"] == "llm" and out["reply"] == "You are at X%."
    assert out["tool_calls"] == [{"tool": "get_attendance", "input": {"subject": "DBMS"}}]


def test_llm_failure_falls_back_to_offline():
    class Down:
        messages = None
        def __init__(self): self.messages = self
        def create(self, **kw): raise ConnectionError("no network")
    s = StudentDAO().get_by_reg("REC24CS003")
    out = ChatAgent(role="student", linked_id=s.student_id, client=Down()).chat("my attendance")
    assert out["mode"].startswith("offline") and out["reply"]
