"""小圆冒险规则。界面以副本事务提交，结算、掉落及奖励一起持久化。"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import time
import uuid
from collections import defaultdict
from typing import Any

from store import is_subjective, record_answer, resource_path
import game_skills as skills
import finance

CONFIG = json.loads(resource_path("assets/game_config.json").read_text(encoding="utf-8"))
ECONOMY = json.loads(resource_path("assets/shop_config.json").read_text(encoding="utf-8"))
WONDERS = json.loads(resource_path("assets/wonder_config.json").read_text(encoding="utf-8"))
CONFIG = {**CONFIG, "drop_percent": ECONOMY["boss_drop_percent"],
          "rarity_weights": ECONOMY["rarity_weights"],
          "rarities": {**CONFIG["rarities"], **ECONOMY["rarities"]}}
BIOMES = CONFIG["biomes"]
WORLDS = ({'id': 'accounting', 'name': '会计世界', 'prefix': 'acc', 'subtitle': '从会计基础出发，点亮原创章节地图'}, {'id': 'law', 'name': '经济法世界', 'prefix': 'law', 'subtitle': '穿过法律森林，挑战原创案例守护者'}, {'id': 'finance', 'name': '财管经营世界', 'prefix': 'cg_original_', 'subtitle': '三位主角修复星光账本，20章经营冒险'})
BASE_SKINS = ("xiaoyuan", "orange_adventurer", "xiaobao")
RARITY_NAMES = {k: v["name"] for k, v in CONFIG["rarities"].items()}


def make_catalog() -> dict[str, dict]:
    items: dict[str, dict] = {}

    def add(item_id: str, name: str, category: str, rarity: str = "common", **extras) -> None:
        items[item_id] = {"id": item_id, "name": name, "category": category, "rarity": rarity,
                          "price": CONFIG["rarities"][rarity]["price"], **extras}

    add("xiaoyuan", "小圆 · 金棕主角", "skin", starter=True, character="xiaoyuan")
    add("orange_adventurer", "小团 · 蓝围巾冒险者", "skin", starter=True, character="orange_adventurer")
    add("orange_mage", "小团 · 星蓝法师", "skin", "rare", character="orange_mage")
    add("orange_knight", "小团 · 蓝盾骑士", "skin", "epic", character="orange_knight")
    items["xiaobao"] = {**finance.CONFIG["hero"], "category": "skin", "rarity": "common", "character": "xiaobao", "price": 0, "starter": True}
    for biome in BIOMES:
        add("outfit_" + biome["id"], biome["outfit"], "skin", biome["rarity"], outfit=biome["id"])
        add("souvenir_" + biome["id"], biome["souvenir"], "collection", biome["rarity"], biome=biome["id"])
    for rarity, name in (("common", "初行探险家"), ("rare", "知识守护者"), ("epic", "星海征服者")):
        add("title_" + rarity, name, "collection", rarity, title=True)
    for slot, label in (("xp", "经验护符"), ("coins", "金币铃铛")):
        for rarity, definition in CONFIG["rarities"].items():
            if "bonus_percent" not in definition:
                continue
            add("equipment_" + slot + "_" + rarity, definition["name"] + label, "equipment", rarity,
                slot=slot, bonus_percent=definition["bonus_percent"])
    items.update({item["id"]: item for item in WONDERS["items"]})
    for item in finance.CONFIG["outfits"]:
        items[item["id"]] = {**item, "category": "skin"}
    for item in finance.CONFIG["companions"]:
        items[item["id"]] = {**item, "category": "companion", "rarity": "rare", "story_only": True}
    for item in finance.CONFIG["props"]:
        items[item["id"]] = {**item, "category": "collection", "rarity": "epic" if item["price"] >= 600 else "rare" if item["price"] >= 300 else "common"}
    for item in finance.CONFIG["commissions"]:
        act = next(a for a in finance.CONFIG["acts"] if a["id"] == item["act_id"])
        npc = next(n for n in finance.CONFIG["npcs"] if n["id"] == (act.get("npc_id") or act.get("npc")))
        items[item["postcard"]] = {"id": item["postcard"], "name": item["name"] + " · 明信片",
                                  "category": "collection", "rarity": "common", "price": 0,
                                  "starter": True, "earned_only": True, "asset": npc["asset"]}
    return items


CATALOG = make_catalog()


def build_campaign(questions: list[dict]) -> dict:
    """读取独立原创地图，必须与实际加载题号全量匹配。"""
    installed = json.loads(resource_path("data/campaign.json").read_text(encoding="utf-8"))
    ids = [q["id"] for q in questions]
    arranged = [qid for level in installed["levels"].values() for qid in level["qids"]]
    bank_meta = json.loads(resource_path("data/questions.json").read_text(encoding="utf-8"))
    if len(ids) != len(set(ids)) or sorted(ids) != sorted(arranged) or installed["bank_fingerprint"] != bank_meta["bank_fingerprint"]:
        raise ValueError("原创地图与题库不一致，请重新同步公开内容。")
    descriptions = {world["id"]: world["subtitle"] for world in WORLDS}
    for world in installed["worlds"]:
        world.setdefault("subtitle", descriptions[world["id"]])
    return copy.deepcopy(installed)


def default_game(questions: list[dict]) -> dict:
    return {"schema_version": 1, "campaign": build_campaign(questions), "results": {},
            "active": None, "paused": {}, "last_result": None, "coins": 0, "xp": 0,
            "inventory": list(BASE_SKINS), "equipment": {"xp": None, "coins": None, "wonder": None},
            "growth_version": 2, "wishlist": "wonder_broom",
            "skill_state": {"schema_version": 1, "purchased": {}, "used": {}, "queued": {}, "ink": 0},
            "skin": "xiaoyuan", "outfit": None, "title": None, "world": "accounting",
            "expedition_round": 1, "expedition_stages": {}, "badges": []}


def ensure_game(progress: dict, questions: list[dict]) -> dict:
    g = progress.get("game")
    if progress.get("bank_family") not in (None, "original") or isinstance(g, dict) and g.get("bank_family") not in (None, "original"):
        raise ValueError("这份备份属于另一种题库，请在对应版本恢复；原存档未修改。")
    if not isinstance(g, dict) or not isinstance(g.get("campaign"), dict):
        g = default_game(questions)
        progress["game"] = g
    qmap = {q["id"]: q for q in questions}
    installed = build_campaign(questions)
    if g["campaign"] != installed:
        baseline_path = resource_path("assets/finance_migration.json")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {}
        trusted = baseline.get("public_campaign")
        if g["campaign"] != trusted:
            raise ValueError("保存的地图与受信题库不一致，原存档已保留，请使用对应版本或备份。")
        old_levels = g["campaign"]["levels"]
        if any(installed["levels"].get(sid) != level for sid, level in old_levels.items()):
            raise ValueError("旧关卡发生变化，不能自动迁移学习进度。")
        if all(g.get("results", {}).get(sid, {}).get("cleared") for sid in old_levels) or g.get("expedition_stages"):
            g["expedition_unlocked"] = True
        g["campaign"] = installed
    for level in g["campaign"]["levels"].values():
        if not level.get("qids") or any(qid not in qmap for qid in level["qids"]):
            raise ValueError("保存的地图与题库不一致，请恢复原题库后再续关。")
    for key, value in {"results": {}, "active": None, "paused": {}, "last_result": None,
                       "coins": 0, "xp": 0, "inventory": list(BASE_SKINS),
                       "equipment": {"xp": None, "coins": None}, "skin": "xiaoyuan",
                       "outfit": None, "title": None, "world": "accounting",
                       "expedition_round": 1, "expedition_stages": {}, "badges": []}.items():
        g.setdefault(key, copy.deepcopy(value))
    # 迁移只补齐结构；不补发旧关奖励，也不修改已开始挑战的加成快照。
    g["growth_version"] = 2
    g["equipment"].setdefault("wonder", None)
    g.setdefault("wishlist", "wonder_broom")
    skills.state(g)
    g["bank_family"] = "original"
    progress["bank_family"] = "original"
    finance.state(g)
    if "xiaobao" not in g["inventory"]:
        g["inventory"].append("xiaobao")
    return g


def level_for(g: dict, stage_id: str) -> dict:
    if stage_id in g["campaign"]["levels"]:
        return g["campaign"]["levels"][stage_id]
    return g["expedition_stages"][stage_id]


def cleared(g: dict, stage_id: str) -> bool:
    return bool(g["results"].get(stage_id, {}).get("cleared"))


def world_stages(g: dict, world_id: str) -> list[str]:
    world = next(w for w in g["campaign"]["worlds"] if w["id"] == world_id)
    return [sid for chapter in world["chapters"] for sid in chapter["stages"]]


def can_play(g: dict, stage_id: str) -> bool:
    if stage_id.startswith("expedition:"):
        return expedition_available(g) and stage_id in g["expedition_stages"]
    level = level_for(g, stage_id)
    ordered = world_stages(g, level["world_id"])
    index = ordered.index(stage_id)
    return index == 0 or cleared(g, ordered[index - 1])


def campaign_complete(g: dict) -> bool:
    return bool(g["campaign"]["levels"]) and all(cleared(g, sid) for sid in g["campaign"]["levels"])


def expedition_available(g: dict) -> bool:
    return bool(g.get("expedition_unlocked")) or campaign_complete(g)


def chapter_complete(g: dict, chapter: dict) -> bool:
    return all(cleared(g, sid) for sid in chapter["stages"])


def next_stage(g: dict, stage_id: str | None = None, world_id: str | None = None) -> str | None:
    if stage_id and stage_id.startswith("expedition:"):
        return None
    world_id = world_id or (level_for(g, stage_id)["world_id"] if stage_id else g["world"])
    ordered = world_stages(g, world_id)
    if stage_id:
        index = ordered.index(stage_id)
        return ordered[index + 1] if index + 1 < len(ordered) else None
    return next((sid for sid in ordered if not cleared(g, sid)), ordered[-1] if ordered else None)


def equipment_bonuses(g: dict) -> dict[str, int]:
    wonder = CATALOG.get(g["equipment"].get("wonder"), {})
    return {slot: int(CATALOG.get(g["equipment"].get(slot), {}).get("bonus_percent", 0))
            + int(wonder.get(slot + "_percent", 0)) for slot in ("xp", "coins")}


def start_attempt(progress: dict, stage_id: str, *, restart: bool = False,
                  rng: Any = None) -> dict:
    g = progress["game"]
    if not can_play(g, stage_id):
        raise ValueError("请先通关前一关。")
    current = g["active"]
    if current and current["stage_id"] == stage_id and not current["settled"] and not restart:
        return current
    if current and not current["settled"] and current["stage_id"] != stage_id:
        g["paused"][current["stage_id"]] = current
    resumed = g["paused"].pop(stage_id, None)
    if resumed and not restart:
        g["active"] = resumed
        return resumed
    qids = list(level_for(g, stage_id)["qids"])
    (rng or random.SystemRandom()).shuffle(qids)
    attempt = {"id": uuid.uuid4().hex, "stage_id": stage_id, "qids": qids,
               "answers": {}, "drafts": {}, "references": [], "index": 0,
               "bonuses": equipment_bonuses(g), "settled": False, "result": None}
    g["active"] = attempt
    skills.apply_boosts(g, attempt, level_for(g, stage_id))
    return attempt


def submit_answer(progress: dict, question: dict, user_answer: str, correct: bool) -> bool:
    attempt = progress["game"]["active"]
    if not attempt or attempt["settled"]:
        raise ValueError("当前没有进行中的挑战。")
    qid = question["id"]
    if qid not in attempt["qids"]:
        raise ValueError("题目不属于当前挑战。")
    if qid in attempt["answers"]:
        return False
    if not user_answer.strip():
        raise ValueError("请先填写或选择答案。")
    if is_subjective(question) and qid not in attempt["references"]:
        raise ValueError("请先查看参考答案，再对照自评。")
    rec = {"correct": bool(correct), "user_answer": user_answer, "ts": time.time()}
    attempt["answers"][qid] = rec
    record_answer(progress, qid, correct, user_answer)
    return True


def stars_for(correct: int, total: int) -> int:
    if not total or correct < 0 or correct > total:
        return 0
    if correct == total:
        return 3
    if correct * 100 >= total * CONFIG["two_star_percent"]:
        return 2
    if correct * 100 >= total * CONFIG["pass_percent"]:
        return 1
    return 0


def weighted_choice(weights: dict[str, int], rng: Any) -> str:
    roll = rng.randrange(sum(weights.values()))
    cumulative = 0
    for key, weight in weights.items():
        cumulative += weight
        if roll < cumulative:
            return key
    raise AssertionError("概率配置为空。")


def quality_for(correct: int, total: int) -> str:
    stars = stars_for(correct, total)
    return "高质量通关" if stars >= 2 else "通关" if stars == 1 else "未通关"


def roll_loot(g: dict, rng: Any) -> dict:
    if rng.randrange(100) >= CONFIG["drop_percent"]:
        return {"kind": "none", "name": "这次没有额外掉落", "coins": 0, "xp": 0}
    category = weighted_choice(CONFIG["category_weights"], rng)
    if category in ("coins", "xp"):
        amount = CONFIG["bonus_" + category]
        return {"kind": category, "name": "金币补给" if category == "coins" else "经验补给",
                "coins": amount if category == "coins" else 0, "xp": amount if category == "xp" else 0}
    rarity = weighted_choice(CONFIG["rarity_weights"], rng)
    pool = [item for item in CATALOG.values() if item["category"] == category
            and item["rarity"] == rarity and not item.get("starter") and not item.get("story_only")]
    if not pool:
        rarity = "epic"
        pool = [item for item in CATALOG.values() if item["category"] == category
                and item["rarity"] == rarity and not item.get("starter") and not item.get("story_only")]
    item = rng.choice(pool)
    duplicate = item["id"] in g["inventory"]
    coins = CONFIG["rarities"][rarity]["duplicate_coins"] if duplicate else 0
    if not duplicate:
        g["inventory"].append(item["id"])
    return {"kind": category, "name": item["name"], "item_id": item["id"], "rarity": rarity,
            "duplicate": duplicate, "coins": coins, "xp": 0}


def roll_surprise(g: dict, rng: Any) -> list[dict]:
    if rng.randrange(100) >= ECONOMY["surprise_percent"]:
        return []
    if weighted_choice(ECONOMY["surprise_kind_weights"], rng) == "ink":
        skills.state(g)["ink"] += 1
        return [{"kind": "ink", "name": "魔法墨水", "amount": 1}]
    rarity = weighted_choice(ECONOMY["surprise_rarity_weights"], rng)
    item = rng.choice([i for i in WONDERS["items"] if i["rarity"] == rarity])
    duplicate = item["id"] in g["inventory"]
    coins = CONFIG["rarities"][rarity]["duplicate_coins"] if duplicate else 0
    if not duplicate:
        g["inventory"].append(item["id"])
    g["coins"] += coins
    return [{"kind": "item", "id": item["id"], "name": item["name"], "rarity": rarity,
             "duplicate": duplicate, "coins": coins}]


def settle_attempt(progress: dict, *, rng: Any = None, surprise_rng: Any = None) -> dict:
    g = progress["game"]
    attempt = g["active"]
    if not attempt:
        raise ValueError("当前没有挑战。")
    if attempt["settled"]:
        return attempt["result"]
    qids = attempt["qids"]
    if not all(qid in attempt["answers"] for qid in qids):
        raise ValueError("请完成本关全部题目后再结算。")
    total = len(qids)
    correct = sum(bool(attempt["answers"][qid]["correct"]) for qid in qids)
    level = level_for(g, attempt["stage_id"])
    assisted = (attempt.get("skill_clear") == "mercy" and level["kind"] in skills.CONFIG["mercy_kinds"]
                and correct >= skills.CONFIG["mercy_min_correct"]
                and correct == math.ceil(total * CONFIG["pass_percent"] / 100) - skills.CONFIG["mercy_extra_wrong"])
    stars = stars_for(correct, total) or (1 if assisted else 0)
    passed = stars > 0
    previous = g["results"].get(level["id"], {})
    first_clear = passed and not previous.get("cleared")
    new_stars = max(0, stars - previous.get("best_stars", 0)) if passed else 0
    xp = new_stars * CONFIG["star_xp"]
    coins = (max(0, max(0, stars - 1) - max(0, previous.get("best_stars", 0) - 1))
             * ECONOMY["quality_star_coins"]) if passed else 0
    loot = None
    if first_clear:
        xp += CONFIG["boss_xp"] if level["kind"] == "boss" else CONFIG["normal_xp"]
        coins += (CONFIG["boss_coins"] if level["kind"] == "boss" else ECONOMY["expedition_coins"]
                  if level["kind"] == "expedition" else ECONOMY["normal_coins"])
        if level["kind"] == "boss":
            # 挑战 ID 已在开始时持久化；未能写盘的结算在退出重启后
            # 仍得到同一个随机结果，避免通过保存失败反复重抽。
            loot = roll_loot(g, rng if rng is not None else random.Random(attempt["id"]))
            xp += loot["xp"]
            coins += loot["coins"]
    level_before = skills.level(g)
    xp = xp * (100 + attempt["bonuses"].get("xp", 0)) // 100
    coins = coins * (100 + attempt["bonuses"].get("coins", 0)) // 100
    g["xp"] += xp
    g["coins"] += coins
    if passed:
        g["results"][level["id"]] = {"cleared": True, "best_stars": max(stars, previous.get("best_stars", 0)),
            "best_correct": max(correct, previous.get("best_correct", 0)), "total": total,
            "first_loot": loot if first_clear else previous.get("first_loot"),
            "first_attempt_id": attempt["id"] if first_clear else previous.get("first_attempt_id"),
            "assisted": assisted or bool(previous.get("assisted")),
            "first_surprise": previous.get("first_surprise", [])}
        if level["kind"] == "expedition":
            g["expedition_round"] = max(g["expedition_round"], level["round"] + 1)
        for world in g["campaign"]["worlds"]:
            for chapter in world["chapters"]:
                if chapter_complete(g, chapter) and chapter["id"] not in g["badges"]:
                    g["badges"].append(chapter["id"])
    growth = roll_surprise(g, surprise_rng if surprise_rng is not None else random.Random(attempt["id"] + ":surprise")) if first_clear and level["kind"] != "expedition" else []
    finance_awards = finance.award_chapters(g)
    if first_clear:
        g["results"][level["id"]]["first_surprise"] = growth
    result = {"attempt_id": attempt["id"], "stage_id": level["id"], "passed": passed,
              "stars": stars, "quality": "技能通关" if assisted else quality_for(correct, total),
              "assisted": assisted, "skill_name": "瞒天过海" if assisted else "",
              "correct": correct, "total": total, "xp": xp, "coins": coins,
              "first_clear": first_clear, "loot": loot, "growth": growth,
              "level_before": level_before, "level_after": skills.level(g),
              "new_skills": [s["id"] for s in skills.CONFIG["definitions"] if level_before < s["level"] <= skills.level(g)],
              "finance_awards": finance_awards,
              "wrong_qids": [qid for qid in qids if not attempt["answers"][qid]["correct"]]}
    attempt["settled"] = True
    attempt["result"] = result
    g["last_result"] = result
    return result


def use_mercy(progress: dict) -> dict:
    g, a = progress["game"], progress["game"]["active"]
    if a and (a.get("result") or {}).get("assisted"):
        return a["result"]
    status = skills.mercy_status(g, a, level_for(g, a["stage_id"]) if a else {})
    if not status["eligible"]:
        raise ValueError(status["reason"])
    skills.use(g, "mercy")
    a.update(skill_clear="mercy", settled=False, result=None)
    return settle_attempt(progress)


def growth_status(g: dict) -> list[dict]:
    count = stats(g)["cleared"]
    return [{**m, "owned": m["item"] in g["inventory"], "unlocked": count >= m["clears"],
             "remaining": max(0, m["clears"] - count)} for m in WONDERS["milestones"]]


def buy_item(progress: dict, item_id: str) -> dict:
    g = progress["game"]
    item = CATALOG[item_id]
    if item.get("earned_only"):
        raise ValueError("完成对应经营委托即可获得这张明信片。")
    if item.get("story_only"):
        return finance.recruit(progress, item_id)
    if item_id in g["inventory"]:
        raise ValueError("已经拥有这件物品。")
    if item.get("starter"):
        raise ValueError("初始形象无需购买。")
    milestone = next((m for m in growth_status(g) if m["item"] == item_id), None)
    if milestone and not milestone["unlocked"]:
        raise ValueError(f"首次通关 {milestone['clears']} 个主线关卡后上架。")
    if g["coins"] < item["price"]:
        raise ValueError("金币不足，先去挑战章节 Boss 吧。")
    g["coins"] -= item["price"]
    g["inventory"].append(item_id)
    return item


def equip_item(progress: dict, item_id: str) -> None:
    g = progress["game"]
    if item_id not in g["inventory"]:
        raise ValueError("尚未拥有这件物品。")
    item = CATALOG[item_id]
    if item["category"] == "equipment":
        slot = item["slot"]
        g["equipment"][slot] = None if g["equipment"].get(slot) == item_id else item_id
    elif item.get("character"):
        g["skin"] = item_id
        worn = CATALOG.get(g.get("outfit"), {})
        fit = worn.get("fit_character")
        if fit and not (fit == item_id or fit == "orange_adventurer" and item_id.startswith("orange_")):
            g["outfit"] = None
    elif item.get("outfit"):
        if item.get("fit_character"):
            g["skin"] = item["fit_character"]
        g["outfit"] = None if g["outfit"] == item_id else item_id
    elif item.get("story_only"):
        finance.equip_companion(progress, item_id)
    elif item.get("title"):
        g["title"] = None if g["title"] == item_id else item_id


def create_expedition(progress: dict, questions: list[dict], *, rng: Any = None) -> dict:
    g = progress["game"]
    if not expedition_available(g):
        raise ValueError("通关三科全部主线后，无尽远征就会开启。")
    round_number = g["expedition_round"]
    stage_id = f"expedition:{round_number:06d}"
    if stage_id in g["expedition_stages"]:
        return g["expedition_stages"][stage_id]
    rng = rng or random.SystemRandom()
    qmap = {q["id"]: q for q in questions}
    wrong = [qid for qid in progress.get("wrong_book", []) if qid in qmap]
    chosen = rng.sample(wrong, min(6, len(wrong)))
    answered = progress.get("answered", {})
    chapter_scores: dict[tuple, list[bool]] = defaultdict(list)
    for q in questions:
        if q["id"] in answered:
            chapter_scores[(q.get("book_id"), q.get("chapter_no"))].append(bool(answered[q["id"]].get("correct")))

    def priority(q: dict) -> tuple:
        scores = chapter_scores.get((q.get("book_id"), q.get("chapter_no")), [])
        rate = sum(scores) / len(scores) if scores else -1.0
        return rate, answered.get(q["id"], {}).get("ts", 0)

    wrong_set = set(wrong)
    pool = [q for q in questions if q["id"] not in wrong_set]
    rng.shuffle(pool)
    pool.sort(key=priority)
    chosen += [q["id"] for q in pool[:max(0, 10 - len(chosen))]]
    if len(chosen) < min(10, len(questions)):
        # 极端情况下全题库都在错题本：保持每轮十道、单轮不重复。
        remainder = [q for q in questions if q["id"] not in chosen]
        rng.shuffle(remainder)
        remainder.sort(key=priority)
        chosen += [q["id"] for q in remainder[:10 - len(chosen)]]
    stage = {"id": stage_id, "world_id": "expedition", "chapter_id": "expedition",
             "chapter_no": round_number, "chapter_title": "无尽远征", "biome": BIOMES[(round_number - 1) % 6]["id"],
             "kind": "expedition", "name": f"远征第 {round_number} 关", "qids": chosen,
             "subjective": any(is_subjective(qmap[qid]) for qid in chosen), "round": round_number}
    g["expedition_stages"][stage_id] = stage
    return stage


def stats(g: dict, world_id: str | None = None) -> dict:
    stages = world_stages(g, world_id) if world_id else list(g["campaign"]["levels"])
    return {"cleared": sum(cleared(g, sid) for sid in stages), "total": len(stages),
            "stars": sum(g["results"].get(sid, {}).get("best_stars", 0) for sid in stages),
            "max_stars": 3 * len(stages), "level": g["xp"] // CONFIG["xp_per_level"] + 1}
