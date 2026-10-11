from attendiq.agents.base import Agent
from attendiq.dao import PlanDAO


class PlannerAgent(Agent):
    name = "PlannerAgent"
    purpose = "Builds a personalised recovery plan for every subject that is short or close to the limit."

    def __init__(self, calculator=None):
        super().__init__(calculator)
        self.plans = PlanDAO()

    def plan_for(self, stat: dict, spare_subjects: list) -> dict:
        thr = f"{float(self.calc.threshold):g}"
        name, pct = stat["subject_name"], stat["percentage"]
        a, t = stat["attended"], stat["total"]
        if stat["status"] == "Shortage":
            need, remaining = stat["classes_needed"], stat["remaining"]
            text = (f"{name}: attendance is {pct}% ({a}/{t}). Attend the next {need} classes without a miss "
                    f"to reach {thr}%.")
            if need > remaining:
                text += (f" Only {remaining} classes remain, so even perfect attendance cannot reach {thr}% - "
                         f"speak to your faculty or HOD about condonation now.")
            else:
                text += f" {remaining} classes remain, which leaves {remaining - need} classes of slack."
            if spare_subjects:
                text += " Subjects where you can still afford a miss: " + ", ".join(
                    f"{s['subject_name']} ({s['safe_bunks']})" for s in spare_subjects) + "."
            return {"classes_needed": need, "plan_text": text}
        # Warning
        text = (f"{name}: {pct}% is only just above {thr}%. You can miss at most {stat['safe_bunks']} more "
                f"class(es) before dropping into shortage.")
        return {"classes_needed": 0, "plan_text": text}

    def run(self, context: dict) -> dict:
        stats = context.get("stats")
        if stats is None:
            stats = self.service.stats(student_ids=context.get("student_ids"))
            context["stats"] = stats
        by_student = {}
        for s in stats:
            by_student.setdefault(s["student_id"], []).append(s)

        created, plans_out = 0, []
        for student_id, rows in by_student.items():
            spare = sorted([r for r in rows if r["status"] == "Safe" and r["safe_bunks"] > 0],
                           key=lambda r: -r["safe_bunks"])[:3]
            for r in rows:
                if r["status"] in ("Shortage", "Warning"):
                    plan = self.plan_for(r, spare)
                    self.plans.replace(student_id, r["subject_id"], plan["classes_needed"], plan["plan_text"])
                    plans_out.append({"student_id": student_id, "subject_id": r["subject_id"], **plan})
                    created += 1
                else:
                    self.plans.clear(student_id, r["subject_id"])   # recovered: drop the stale plan
        context["plans"] = plans_out
        return {"plans_created": created}
