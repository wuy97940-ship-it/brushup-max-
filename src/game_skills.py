"""等级技能：次数、排除提示与加成都在存档事务中变更。"""
from __future__ import annotations

import json
import math
import re
import uuid

from store import is_subjective, resource_path

CONFIG = json.loads(resource_path("assets/skill_config.json").read_text(encoding="utf-8"))
RULES = json.loads(resource_path("assets/game_config.json").read_text(encoding="utf-8"))
DEFINITIONS = {s["id"]: s for s in CONFIG["definitions"]}


def level(g):
    return g["xp"] // RULES["xp_per_level"] + 1


def state(g):
    st = g.setdefault("skill_state", {"schema_version": 1})
    for key in ("purchased", "used", "queued"):
        st.setdefault(key, {})
    st.setdefault("ink", 0)
    return st


def available(g, skill_id):
    s = DEFINITIONS.get(skill_id)
    if not s or level(g) < s["level"]:
        return 0
    st = g.get("skill_state", {})
    return max(0, 1 + st.get("purchased", {}).get(skill_id, 0) - st.get("used", {}).get(skill_id, 0))


def use(g, skill_id):
    if not available(g, skill_id):
        raise ValueError("技能尚未解锁或次数不足，可在成长页用金币或魔法墨水补充。")
    st = state(g)
    st["used"][skill_id] = st["used"].get(skill_id, 0) + 1


def refill(progress, skill_id, with_ink=False):
    g = progress["game"]
    s = DEFINITIONS[skill_id]
    if level(g) < s["level"]:
        raise ValueError("请先达到技能解锁等级。")
    st = state(g)
    if with_ink:
        if st["ink"] < 1:
            raise ValueError("魔法墨水可在主线首次通关的低概率惊喜中获得。")
        st["ink"] -= 1
    else:
        if g["coins"] < s["price"]:
            raise ValueError("金币不足。")
        g["coins"] -= s["price"]
    st["purchased"][skill_id] = st["purchased"].get(skill_id, 0) + 1
    return s


def queue(progress, skill_id):
    g, s = progress["game"], DEFINITIONS[skill_id]
    if s["type"] != "boost":
        raise ValueError("请在对应答题页面使用此技能。")
    st = state(g)
    if st["queued"].get(skill_id):
        del st["queued"][skill_id]
        return {"queued": False}
    if not available(g, skill_id):
        raise ValueError("技能尚未解锁或次数不足。")
    st["queued"][skill_id] = True
    return {"queued": True}


def apply_boosts(g, attempt, stage):
    st = state(g)
    for skill_id in ("gold", "focus"):
        s = DEFINITIONS[skill_id]
        if (not st["queued"].get(skill_id) or not available(g, skill_id)
                or g["results"].get(attempt["stage_id"], {}).get("cleared")
                or (skill_id == "gold" and stage["kind"] != "boss")):
            continue
        use(g, skill_id)
        del st["queued"][skill_id]
        attempt["bonuses"][s["slot"]] = attempt["bonuses"].get(s["slot"], 0) + s["bonus_percent"]
        attempt.setdefault("skills_used", []).append(skill_id)


def mercy_status(g, attempt, stage):
    if not attempt or not attempt["settled"] or attempt.get("result", {}).get("passed"):
        return {"eligible": False, "reason": "完成本轮作答后使用"}
    if g["results"].get(attempt["stage_id"], {}).get("cleared"):
        return {"eligible": False, "reason": "这一关已经解锁，无需消耗技能"}
    if stage["kind"] not in CONFIG["mercy_kinds"]:
        return {"eligible": False, "reason": "Boss 仍按 70% 通关"}
    total = len(attempt["qids"])
    correct = sum(bool(a["correct"]) for a in attempt["answers"].values())
    required = math.ceil(total * RULES["pass_percent"] / 100)
    if correct < CONFIG["mercy_min_correct"] or correct != required - CONFIG["mercy_extra_wrong"]:
        return {"eligible": False, "reason": "距离通关线只差一题时可用"}
    return {"eligible": True, "available": available(g, "mercy"), "correct": correct, "required": required}


def start_practice(progress, qids, name, restart=False):
    if not qids:
        raise ValueError("当前筛选没有可刷题目。")
    a = progress.get("practice")
    if a and a.get("qids") == qids and not a.get("settled") and not restart:
        return a
    a = {"id": "practice-" + uuid.uuid4().hex, "qids": list(qids), "name": name,
         "answers": {}, "drafts": {}, "references": [], "index": 0, "settled": False}
    progress["practice"] = a
    return a


def hint(progress, question, practice=False):
    g, qid = progress["game"], question["id"]
    a = progress.get("practice") if practice else g["active"]
    if not a or a["settled"] or qid in a["answers"] or qid not in a["qids"] or is_subjective(question):
        raise ValueError("请在尚未提交的客观题上使用。")
    if qid in a.get("hints", {}):
        return a["hints"][qid]
    if a.get("hint_used"):
        raise ValueError("每场挑战最多使用一次灵光一现。")
    options = list(question.get("options", {}))
    right = set(re.sub(r"[,，、\s]", "", str(question["answer"])))
    wrong = [key for key in options if key not in right]
    if len(options) < 3 or not wrong:
        raise ValueError("本题不适合排除选项。")
    use(g, "insight")
    a.setdefault("hints", {})[qid] = [wrong[0]]
    a["hint_used"] = True
    return a["hints"][qid]


def outline(progress, question, practice=False):
    g, qid = progress["game"], question["id"]
    a = progress.get("practice") if practice else g["active"]
    if (not a or a["settled"] or qid not in a["qids"] or not is_subjective(question)
            or qid not in a["references"] or not a["drafts"].get(qid, "").strip()):
        raise ValueError("请先填写主观题并查看参考答案。")
    text = str(question.get("answer", "")).strip()
    pattern = r"[（(]?\s*(?:参见|详见|见)(?:上方|下方)?(?:的)?(?:答案区|解析区|解析|参考答案|答案|详解)\s*[）)]?[。.]?"
    placeholder = re.fullmatch(pattern, text)
    if not text or placeholder:
        text = str(question.get("explanation", "")).strip()
    if not text:
        raise ValueError("本题没有可整理的参考答案。")
    cards = [t.strip() for t in re.split(r"\n+", text) if t.strip()]
    cards = cards if len(cards) > 1 else re.findall(r"[^。]+。?", text)
    if qid in a.get("outlines", {}):
        # 修复旧版已生成的占位卡片，不重复消耗次数。
        if re.fullmatch(pattern, "".join(a["outlines"][qid])):
            a["outlines"][qid] = cards
        return a["outlines"][qid]
    use(g, "outline")
    a.setdefault("outlines", {})[qid] = cards
    return a["outlines"][qid]


def view(g):
    return [{**s, "unlocked": level(g) >= s["level"], "charges": available(g, s["id"]),
             "queued": bool(g.get("skill_state", {}).get("queued", {}).get(s["id"])),
             "xp_remaining": max(0, (s["level"] - 1) * RULES["xp_per_level"] - g["xp"])}
            for s in CONFIG["definitions"]]
