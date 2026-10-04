"""财管经营篇：精确数值核对、分小问作答与离线小镇规则。"""
from __future__ import annotations

import copy
import json
import re
import time
from decimal import Decimal, InvalidOperation, localcontext

from store import resource_path

CONFIG = json.loads(resource_path("assets/finance_config.json").read_text(encoding="utf-8"))
UNITS = {"元": ("money", 0), "万元": ("money", 4), "%": ("ratio", -2),
         "小数": ("ratio", 0), "件": ("count", 0), "年": ("years", 0), "无单位": ("scalar", 0)}


def state(g: dict) -> dict:
    defaults = {"version": 1, "schema_version": 1, "materials": 0, "chapter_claims": {},
                "buildings": {}, "companion": None, "story_seen": [], "commission_claims": {},
                "diary": [], "formula_seen": [],
                "tools": {"scratch": "", "focus_started_at": None, "focus_seconds": 1500}}
    if not isinstance(g.get("finance_expansion"), dict):
        g["finance_expansion"] = copy.deepcopy(defaults)
    for key, value in defaults.items():
        g["finance_expansion"].setdefault(key, copy.deepcopy(value))
    return g["finance_expansion"]


def numeric_check(check: dict, value: str, unit: str | None = None) -> dict:
    target_unit = check.get("unit") or "无单位"
    result = {"key": check["key"], "label": check.get("label", ""), "correct": False,
              "message": "请输入有效数值", "expected": str(check["value"]), "unit": target_unit}
    try:
        text = str(value if value is not None else "").strip().replace("−", "-")
        source_unit = unit or target_unit
        suffix = re.search(r"(万元|元|小数|件|年|%|％)$", text)
        if suffix:
            source_unit = suffix[1].replace("％", "%")
            text = text[:suffix.start()].strip()
        source, target = UNITS.get(source_unit), UNITS.get(target_unit)
        if not source or not target or source[0] != target[0]:
            result["message"] = "单位不匹配"
            return result
        text = text.replace(",", "").replace("，", "")
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
            return result
        if len(re.sub(r"\D", "", text)) > 100:
            return result
        with localcontext() as context:
            context.prec = 240
            expected = Decimal(str(check["value"]))
            actual = Decimal(text) * (Decimal(10) ** (source[1] - target[1]))
            if not expected.is_finite() or not actual.is_finite():
                return result
            places = check.get("decimals")
            if not isinstance(places, int):
                places = max(0, -expected.as_tuple().exponent)
            if not 0 <= places <= 30:
                return result
            tolerance = Decimal(0) if check.get("exact") else Decimal("0.5") * Decimal(10) ** -places
            result["correct"] = abs(actual - expected) <= tolerance
            result["message"] = "数值通过" if result["correct"] else "请核对公式、代入与单位"
    except (ValueError, InvalidOperation, TypeError, OverflowError):
        pass
    return result


def evaluate_numeric(checks: list[dict], values: dict) -> list[dict]:
    results = []
    for check in checks:
        answer = values.get(check["key"], "")
        results.append(numeric_check(check, answer.get("value", ""), answer.get("unit"))
                       if isinstance(answer, dict) else numeric_check(check, answer))
    return results


def draft(attempt: dict, question: dict) -> dict:
    return attempt.setdefault("structured_drafts", {}).setdefault(
        question["id"], {"process": {}, "values": {}, "units": {}})


def prepare_submission(attempt: dict, question: dict) -> dict:
    qid = question["id"]
    if attempt.get("settled") or qid not in attempt["qids"]:
        raise ValueError("题目不属于进行中的挑战。")
    prior = attempt.get("structured_submissions", {}).get(qid)
    if prior and not prior["graded"]:
        return prior
    if qid in attempt["answers"] and not attempt.get("correction_edit", {}).get(qid):
        raise ValueError("首次成绩已保存，点击重新核对可继续练习。")
    current = draft(attempt, question)
    if any(not current["process"].get(sub["id"], "").strip() for sub in question["subquestions"]):
        raise ValueError("请填写每个小问的计算过程或理由。")
    checks = question.get("numeric_checks", [])
    if any(not current["values"].get(check["key"], "").strip() for check in checks):
        raise ValueError("请填写所有可核对的关键数值。")
    submission = {"draft": copy.deepcopy(current), "checks": [
        numeric_check(check, current["values"][check["key"]], current["units"].get(check["key"]) or check.get("unit"))
        for check in checks], "process": {}, "submitted_at": time.time(), "graded": False,
        "correction": qid in attempt["answers"]}
    attempt.setdefault("structured_submissions", {})[qid] = submission
    if qid not in attempt["references"]:
        attempt["references"].append(qid)
    return submission


def grade(attempt: dict, question: dict) -> dict:
    qid = question["id"]
    submission = attempt.get("structured_submissions", {}).get(qid)
    if not submission:
        raise ValueError("请先提交各小问。")
    if submission["graded"]:
        return {"first": False, "record": submission["record"]}
    if any(type(submission["process"].get(sub["id"])) is not bool for sub in question["subquestions"]):
        raise ValueError("请对照参考逐个完成过程自评。")
    correct = all(check["correct"] for check in submission["checks"]) and all(
        submission["process"][sub["id"]] for sub in question["subquestions"])
    user_answer = "\n".join("（" + sub["id"] + "）" + submission["draft"]["process"][sub["id"]]
                            for sub in question["subquestions"])
    user_answer += "\n" + "\n".join(check["label"] + "：" + submission["draft"]["values"][check["key"]] + " "
                                   + (submission["draft"]["units"].get(check["key"]) or check.get("unit", ""))
                                   for check in question.get("numeric_checks", []))
    record = {"correct": correct, "user_answer": user_answer, "ts": time.time(),
              "numeric_results": copy.deepcopy(submission["checks"]), "process": copy.deepcopy(submission["process"])}
    first = qid not in attempt["answers"]
    if first:
        attempt["answers"][qid] = record
    else:
        attempt.setdefault("corrections", {}).setdefault(qid, []).append(record)
    submission.update(graded=True, record=record)
    attempt.setdefault("correction_edit", {}).pop(qid, None)
    return {"first": first, "record": record}


def begin_correction(attempt: dict, question: dict) -> None:
    qid = question["id"]
    if qid not in attempt["answers"] or attempt.get("settled"):
        raise ValueError("本轮结束前可以重新核对，结束后请开启新的练习。")
    attempt.setdefault("correction_edit", {})[qid] = True
    attempt.setdefault("structured_submissions", {}).pop(qid, None)


def chapters(g: dict) -> list[dict]:
    return next((w["chapters"] for w in g["campaign"]["worlds"] if w["id"] == "finance"), [])


def chapter_cleared(g: dict, chapter: dict) -> bool:
    return bool(chapter["stages"]) and all(g["results"].get(sid, {}).get("cleared") for sid in chapter["stages"])


def award_chapters(g: dict) -> list[dict]:
    current, awards = state(g), []
    for chapter in chapters(g):
        number = chapter["number"]
        if 1 <= number <= 20 and chapter_cleared(g, chapter) and not current["chapter_claims"].get(str(number)):
            current["chapter_claims"][str(number)] = True
            current["materials"] += CONFIG["chapter_materials"]
            awards.append({"chapter": number, "materials": CONFIG["chapter_materials"]})
    return awards


def act_open(g: dict, act: dict) -> bool:
    by_number = {c["number"]: c for c in chapters(g)}
    start = min(act["chapters"])
    return start in by_number and all(number in by_number and chapter_cleared(g, by_number[number])
                                     for number in range(1, start))


def view(g: dict) -> dict:
    current, cs = state(g), {c["number"]: c for c in chapters(g)}
    acts = [{**a, "open": act_open(g, a),
             "completed": all(n in cs and chapter_cleared(g, cs[n]) for n in a["chapters"]),
             "seen": a["id"] in current["story_seen"]} for a in CONFIG["acts"]]
    buildings = [{**b, "level": current["buildings"].get(b["id"], 0),
                  "open": next(a["open"] for a in acts if a["id"] == b["act_id"])} for b in CONFIG["buildings"]]
    for building in buildings:
        building["cost"] = CONFIG["building_costs"][building["level"]] if building["level"] < 3 else 0
    return {"materials": current["materials"], "acts": acts, "buildings": buildings,
            "companions": [{**c, "owned": c["id"] in g["inventory"],
                            "unlocked": bool(current["chapter_claims"].get(str(c["unlock_chapter"]))),
                            "equipped": c["id"] == current["companion"]} for c in CONFIG["companions"]],
            "commissions": [{**c, "claimed": c["id"] in current["commission_claims"],
                             "open": next(a["open"] for a in acts if a["id"] == c["act_id"])} for c in CONFIG["commissions"]]}


def story_for(g: dict, act_id: str) -> dict:
    act = next(a for a in view(g)["acts"] if a["id"] == act_id)
    if not act["open"]:
        raise ValueError("完成前一区域的学习后，新的故事会开启。")
    return {"act": act, "story": act["story"], "completion_story": act["completion_story"], "completed": act["completed"]}


def mark_story(progress: dict, act_id: str) -> None:
    story_for(progress["game"], act_id)
    seen = state(progress["game"])["story_seen"]
    if act_id not in seen:
        seen.append(act_id)


def upgrade_building(progress: dict, building_id: str) -> dict:
    g = progress["game"]
    building = next((b for b in view(g)["buildings"] if b["id"] == building_id), None)
    if not building or not building["open"]:
        raise ValueError("建筑尚未开放。")
    if building["level"] >= 3:
        raise ValueError("建筑已经成为星光地标。")
    current, cost = state(g), building["cost"]
    if current["materials"] < cost:
        raise ValueError("建材不足，完成新的财管章节可以获得3份建材。")
    current["materials"] -= cost
    current["buildings"][building_id] = building["level"] + 1
    return {"id": building_id, "level": building["level"] + 1, "cost": cost}


def recruit(progress: dict, companion_id: str) -> dict:
    g = progress["game"]
    item = next((c for c in view(g)["companions"] if c["id"] == companion_id), None)
    if not item or not item["unlocked"]:
        raise ValueError("完成伙伴对应章节后，就能邀请它加入。")
    if item["owned"]:
        raise ValueError("这位伙伴已经加入。")
    if g["coins"] < item["price"]:
        raise ValueError("金币不足，继续学习积累金币吧。")
    g["coins"] -= item["price"]
    g["inventory"].append(companion_id)
    return item


def equip_companion(progress: dict, companion_id: str) -> None:
    g = progress["game"]
    if companion_id not in g["inventory"] or not any(c["id"] == companion_id for c in CONFIG["companions"]):
        raise ValueError("请先招募这位伙伴。")
    current = state(g)
    current["companion"] = None if current["companion"] == companion_id else companion_id


def commission_questions(meta: list[dict], commission_id: str) -> list[str]:
    commission = next(c for c in CONFIG["commissions"] if c["id"] == commission_id)
    subjective_types = {"计算分析题", "综合题", "简答题", "论述题", "案例分析题"}
    pool = [q for q in meta if (q.get("book_id", "").startswith("cpa_cg_") or q.get("book_id") == "cg_original_v02")
            and q.get("chapter_no") in commission["chapters"]
            and ((q.get("type") in subjective_types) == (commission["type"] == "subjective"))]
    return [q["id"] for q in sorted(pool, key=lambda q: q["id"])[:commission["amount"]]]


def claim_commission(progress: dict, commission_id: str, attempt: dict) -> dict:
    g, current = progress["game"], state(progress["game"])
    commission = next(c for c in view(g)["commissions"] if c["id"] == commission_id)
    if commission["claimed"]:
        return {"id": commission_id, "already_claimed": True}
    if not commission["open"] or attempt.get("commission_id") != commission_id:
        raise ValueError("请先完成对应经营委托。")
    ids = attempt["qids"]
    if len(ids) != commission["amount"] or any(qid not in attempt["answers"] for qid in ids):
        raise ValueError("请完成委托的全部题目。")
    correct = sum(bool(attempt["answers"][qid]["correct"]) for qid in ids)
    if correct * 100 < len(ids) * 70:
        raise ValueError("继续复盘，达到70%即可完成委托。")
    current["commission_claims"][commission_id] = {"postcard": commission["postcard"], "attempt_id": attempt["id"]}
    if commission["postcard"] not in g["inventory"]:
        g["inventory"].append(commission["postcard"])
    return {"id": commission_id, "postcard": commission["postcard"]}


def rescue_questions(progress: dict, meta: list[dict], world: str) -> list[str]:
    prefixes = {"accounting": ("cpa_kj_", "acc_original_"), "law": ("cpa_jjf_", "law_original_"),
                "finance": ("cpa_cg_", "cg_original_")}
    valid = {q["id"] for q in meta if q.get("book_id", "").startswith(prefixes.get(world, (world,)))}
    return [qid for qid in progress.get("wrong_book", []) if qid in valid][:5]


def knowledge() -> dict:
    path = resource_path("assets/finance_knowledge.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"chapters": []}
