"""电脑版5.1规则：统一商店、角色权益、装备奖励与冒险家园。

规则只修改调用方提供的存档副本，由界面原子落盘后展示结果。
旧题库、旧地图与旧成绩原样保留，新地图使用独立稳定编号。
"""
from __future__ import annotations

import copy
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import random
import time
import uuid
from collections import defaultdict

import store
import desktop_mood as mood
from desktop_market import SHOP_CATALOG, shop_items, SLOTS, PERSONAL_SLOTS, CATEGORIES, SUBCATEGORIES

CONFIG = json.loads(store.resource_path("assets/product_config.json").read_text(encoding="utf-8"))
HEROES = {item["id"]: item for item in CONFIG["heroes"]}
CATALOG = {item["id"]: item for item in CONFIG["items"]}
SKILLS = {item["id"]: item for item in CONFIG["skills"]}
BEIJING = timezone(timedelta(hours=8))
WORLD_DEFINITIONS = (
    ("accounting", "acc_original_v01", "会计世界", "账本城 · 一步步点亮会计知识", "forest"),
    ("law", "law_original_v01", "经济法世界", "法典城 · 穿过条文与案例的森林", "island"),
    ("finance", "cg_original_v02", "财务管理世界", "金融岛 · 用知识照亮星光账本", "stars"),
)


def timestamp(now: float | None = None) -> float:
    return time.time() if now is None else now


def day_key(now: float | None = None) -> str:
    return datetime.fromtimestamp(timestamp(now), BEIJING).date().isoformat()


def state(g: dict) -> dict:
    s = g["product"]
    house = s.get("house")
    if house and str(house["active_floor"]) in house["floors"]:
        s["room"] = house["floors"][str(house["active_floor"])]
    return s


def house_state(g: dict) -> dict:
    s = state(g)
    if "house" not in s:
        s["house"] = {"version": 1, "unlocked_floors": 1, "active_floor": 1, "floors": {"1": s["room"]}}
    return s["house"]


def switch_floor(progress: dict, floor: int) -> dict:
    g = progress["game"]
    house = house_state(g)
    if not isinstance(floor, int) or str(floor) not in house["floors"] or floor > house["unlocked_floors"]:
        raise ValueError("这一层尚未扩建，请去家装商店解锁。")
    house["active_floor"] = floor
    state(g)
    return {"floor": floor, "unlocked_floors": house["unlocked_floors"]}


def hero_id(g: dict) -> str:
    skin = g.get("skin", "xiaoyuan")
    return "orange_adventurer" if skin.startswith("orange_") else skin if skin in HEROES else "xiaoyuan"


_current_hero_id = hero_id


def level(g: dict) -> int:
    xp = max(0, int(g.get("xp", 0)))
    return 1 + xp // 100 if xp < 400 else 5 + (xp - 400) // 200


def capacity(g: dict) -> int:
    rule = CONFIG["energy"]
    return min(rule["capacity_ceiling"], rule["initial_points"] + rule["level_capacity_points"] * (level(g) - 1))


def refresh_capacity(g: dict) -> None:
    if growth.enabled(g):
        growth.collect_honors(g)
    maximum = capacity(g) * 100
    for identifier, hero in state(g)["heroes"].items():
        hero["maximum"] = maximum
        # 升级只增加容量，绝不补当前体力，也不能唤醒休眠角色。
        hero["energy"] = max(0, min(int(hero["energy"]), maximum))
        if growth.enabled(g):
            mana_maximum = growth.mana_maximum(g, identifier)
            if not mana_maximum:
                hero['mana'] = 0
                hero['mana_unlocked'] = False
            elif hero.get('mana_unlocked') is False or 'mana' not in hero:
                hero['mana'] = growth.CONFIG['mana']['initial']
                hero['mana_unlocked'] = True
            else:
                hero.setdefault('mana_unlocked', True)
            hero['mana_maximum'] = mana_maximum
            hero['mana'] = max(0, min(int(hero['mana']), mana_maximum))


def active_hero(g: dict) -> dict:
    identifier = hero_id(g)
    if identifier not in state(g)["heroes"]:
        raise ValueError("请先领取或解锁一位主角。")
    return state(g)["heroes"][identifier]


def materials(g: dict) -> int:
    return int(g.get("finance_expansion", {}).get("materials", 0))


def add_materials(g: dict, amount: int) -> None:
    wallet = g.setdefault("finance_expansion", {})
    wallet["materials"] = materials(g) + amount


def build_routes(questions: list[dict]) -> dict:
    worlds, levels = [], {}
    for world_id, prefix, name, subtitle, biome in WORLD_DEFINITIONS:
        grouped = defaultdict(list)
        for question in questions:
            if question.get("book_id", "").startswith(prefix):
                number = int(question.get("chapter_no") or 0)
                if store.is_subjective(question) and not number:
                    title = question.get("chapter", "")
                    number = 4 if "民法" in title else 8 if "破产" in title else 9 if "票据" in title else 0
                grouped[number].append(question)
        if not grouped:
            continue
        chapters = []
        for number, pool in sorted(grouped.items()):
            chapter_id = f"v5:{world_id}:{number:02d}"
            stages = []
            from desktop_challenge import rank
            objective = [q for q in pool if not store.is_subjective(q)]
            elite = sorted(objective, key=lambda q: (-rank(q), q['type']!='多选题', q['id']))[:10]
            reserved = {q['id'] for q in elite}
            ordinary = [q for q in objective if q['id'] not in reserved]
            subjective = [q for q in pool if store.is_subjective(q)]
            title = pool[0].get("chapter", f"第{number}章")
            def add(kind: str, index: int, group: list[dict], label: str) -> None:
                identifier = f"{chapter_id}:{kind}:{index:03d}"
                stages.append(identifier)
                levels[identifier] = {"id": identifier, "world_id": world_id, "chapter_id": chapter_id,
                    "chapter_no": number, "chapter_title": title, "kind": kind, "name": label,
                    "biome": biome, "qids": [q["id"] for q in group],
                    "subjective": bool(group and store.is_subjective(group[0])), "product_route": True}
            for offset in range(0, len(ordinary), CONFIG["stage_size"]):
                index = offset // CONFIG["stage_size"] + 1
                add("normal", index, ordinary[offset:offset + CONFIG["stage_size"]], f"探索关 {index}")
            for index, question in enumerate(subjective, 1):
                add("case", index, [question], f"案例挑战 {index}")
            if elite:
                add("boss", 1, elite, "章节 Boss · 重难点挑战")
            chapters.append({"id": chapter_id, "number": number, "title": title, "stages": stages, "biome": biome})
        worlds.append({"id": world_id, "name": name, "subtitle": subtitle, "biome": biome, "chapters": chapters})
    included = {qid for item in levels.values() for qid in item["qids"]}
    if included != {q["id"] for q in questions}:
        raise ValueError("新冒险地图未完整覆盖题库，请先核对学科与章节映射。")
    fingerprint = hashlib.sha256("\n".join(sorted(q["id"] for q in questions)).encode("utf-8")).hexdigest()
    return {"version": 3, "bank_fingerprint": fingerprint, "worlds": worlds, "levels": levels}


def _new_hero(g: dict) -> dict:
    return {"energy": capacity(g) * 100, "maximum": capacity(g) * 100, "low_mood": False,
            "mood": CONFIG['mood']['initial'], "mood_version": 1,
            "wrong_streak": [], "correct_streak": 0, "rest_started": None}


def _appearance(identifier: str) -> dict:
    return {"skin": identifier, **{slot: None for slot in PERSONAL_SLOTS}}


def _sync_appearance(g: dict, identifier: str) -> None:
    appearance = state(g)["appearances"].setdefault(identifier, _appearance(identifier))
    g["skin"] = appearance.get("skin", identifier)
    g["outfit"], g["headwear"] = appearance.get("outfit"), appearance.get("headwear")
    for slot in ('footwear', 'pawgear'):
        g[slot] = appearance.get(slot)


def _upgrade_v2(progress: dict, *, from_version: int | None) -> None:
    """一次性收束旧赠角色权益，保留付款凭证与被锁角色原状态。"""
    g, s = progress["game"], state(progress["game"])
    current = hero_id(g)
    paid = {tx.get("item") for tx in s["transactions"].values()
            if tx.get("operation") == "buy" and tx.get("item") in HEROES}
    starter = current if s.get("starter_claimed") or s["heroes"] else None
    unlocked = paid | ({starter} if starter else set())
    s["starter_hero"] = starter
    s["starter_claimed"] = starter is not None
    s["entitlements"] = {identifier: {"source": "purchase" if identifier in paid else "starter"}
                          for identifier in unlocked}
    s["appearances"] = {identifier: _appearance(identifier) for identifier in HEROES}
    if g.get("skin", current) != current:
        s["appearances"][current]["legacy_skin"] = g["skin"]
    s["appearances"][current]["skin"] = current
    old_outfit = g.get("outfit")
    if old_outfit:
        item = SHOP_CATALOG.get(old_outfit, {})
        target = item.get("fit_character") or current
        slot = "headwear" if item.get("slot") == "headwear" else "outfit"
        s["appearances"][target][slot] = old_outfit
    if g.get("headwear"):
        s["appearances"][current]["headwear"] = g["headwear"]
    archived = s.setdefault("archived_heroes", {})
    locked = []
    for identifier in list(s["heroes"]):
        if identifier not in unlocked:
            locked.append(identifier)
            archived[identifier] = {"state": s["heroes"].pop(identifier),
                                    "appearance": s["appearances"].pop(identifier)}
    for identifier in unlocked:
        s["heroes"].setdefault(identifier, _new_hero(g))
    g["inventory"] = [identifier for identifier in g.get("inventory", [])
                       if identifier not in HEROES or identifier in unlocked]
    for identifier in sorted(unlocked):
        if identifier not in g["inventory"]:
            g["inventory"].append(identifier)
    old_clears = sum(bool(rec.get("cleared")) for identifier, rec in g.get("results", {}).items()
                     if identifier in g.get("campaign", {}).get("levels", {}))
    s["wonder_legacy_eligible"] = [identifier for identifier, item in SHOP_CATALOG.items()
        if item.get("required_clears", 10**9) <= old_clears or item.get("slot") == "wonder" and identifier in g["inventory"]]
    s["reward_remainders"] = {"xp": 0, "coins": 0}
    # 存档中已开场的挑战继续沿用原快照；缺失时使用0，不能补领新加成。
    attempts = [g.get("active"), progress.get("practice"), *g.get("paused", {}).values()]
    for attempt in attempts:
        if isinstance(attempt, dict) and not attempt.get("settled"):
            attempt.setdefault("bonuses", {"xp": 0, "coins": 0})
    s["migration"].update(from_version=from_version, to_version=2, locked_heroes=locked,
                          preserved_purchased_heroes=sorted(paid),
                          preserved=["学习记录", "成绩", "金币", "经验", "建材", "背包"],
                          acknowledged=from_version is None)
    s["version"] = 2
    if starter:
        _sync_appearance(g, starter)
    else:
        g["outfit"], g["headwear"] = None, None


def hero_preview(g: dict, identifier: str) -> dict:
    if identifier not in HEROES:
        raise ValueError("请选择有效主角。")
    s = state(g)
    appearance = copy.deepcopy(s["appearances"].get(identifier) or
        s.get("archived_heroes", {}).get(identifier, {}).get("appearance") or _appearance(identifier))
    # 预览只传渲染需要的字段；不复制两份完整地图、成绩及交易历史。
    # 所有可修改字段均独立，试穿不会改变实际穿戴。
    preview = {"skin": identifier, **{slot: appearance.get(slot) for slot in PERSONAL_SLOTS},
               "equipment": copy.deepcopy(g.get("equipment", {})),
               "finance_expansion": copy.deepcopy(g.get("finance_expansion", {})),
               "product": {"settings": dict(s["settings"])}}
    return preview


def owned_count(g: dict, identifier: str) -> int:
    item = SHOP_CATALOG.get(identifier)
    if item is None:
        return int(identifier in g.get("inventory", []))
    if item["kind"] == "hero":
        return int(identifier in state(g)["heroes"])
    count = int(state(g)["stock"].get(identifier, 0))
    if item["category"] == "装备":
        return int(count > 0 or identifier in g.get("inventory", []))
    return count


def is_equipped(g: dict, identifier: str) -> bool:
    item = SHOP_CATALOG.get(identifier, {})
    if item.get("kind") == "hero":
        return hero_id(g) == identifier and bool(owned_count(g, identifier))
    slot = item.get("slot")
    return bool(slot) and (g.get(slot) == identifier if slot in PERSONAL_SLOTS
                           else g.get("equipment", {}).get(slot) == identifier)


def bonuses(g: dict) -> dict:
    result = {'xp': 0, 'coins': 0}
    for slot in SLOTS:
        identifier = g.get(slot) if slot in PERSONAL_SLOTS else g.get('equipment', {}).get(slot)
        item = SHOP_CATALOG.get(identifier, {}) if identifier and owned_count(g, identifier) else {}
        if item.get('fit_character') and item['fit_character'] != hero_id(g):
            continue
        for kind in result:
            result[kind] += int(item.get(kind + '_percent', 0))
    if growth.enabled(g):
        bond = growth.bond_bonuses(g)
        for kind in result:
            result[kind] += bond[kind]
    return result


equipment_bonuses = bonuses


def purchase_status(g: dict, identifier: str) -> dict:
    if identifier not in SHOP_CATALOG:
        return {"allowed": False, "reason": "这件物品尚未在商店上架。", "owned": 0}
    item = SHOP_CATALOG[identifier]
    owned = owned_count(g, identifier)
    balance = int(g.get("coins", 0)) if item["currency"] == "coins" else materials(g)
    count = sum(bool(rec.get("cleared")) and not rec.get("legacy_migrated")
                for key, rec in g.get("results", {}).items() if key in g.get("product_campaign", {}).get("levels", {}))
    needed = item.get("required_clears", 0)
    unlocked = count >= needed or identifier in state(g).get("wonder_legacy_eligible", [])
    reason = ""
    if not state(g)["starter_claimed"] and item["kind"] == "hero":
        reason = "请先选择一位免费主角。"
    elif owned >= item.get("max_quantity", 999):
        reason = "已经拥有这件物品。" if item.get("max_quantity") == 1 else "已经达到拥有数量上限。"
    elif item["kind"] == "hero":
        reason = "请到角色馆参加100题主角考试，通过后支付尾款。"
    elif item.get("fit_character") and item["fit_character"] not in state(g)["heroes"]:
        reason = "请先解锁这套服装对应的主角。"
    elif not unlocked:
        reason = f"首次通关{needed}个新版独立关卡后上架，还差{max(0, needed - count)}关。"
    elif item.get("kind") == "floor_upgrade" and house_state(g)["unlocked_floors"] != item["target_floor"]-1:
        reason = "请先扩建二楼，再解锁三楼。" if item["target_floor"] == 3 else "这一层已扩建。"
    elif balance < item["price"]:
        reason = f"{'金币' if item['currency'] == 'coins' else '建材'}不足，还差{item['price'] - balance}。"
    return {"allowed": not reason, "reason": reason, "owned": owned, "price": item["price"],
            "currency": item["currency"], "balance": balance, "equipped": is_equipped(g, identifier),
            "unlocked": unlocked, "required_clears": needed, "cleared": count,
            "remaining_clears": max(0, needed - count) if not unlocked else 0}


def _reward_with_bonus(g: dict, amount: int, slot: str, snapshot: dict, *, ceiling: int | None = None) -> int:
    if amount <= 0 or ceiling == 0:
        return 0
    remainders = state(g)["reward_remainders"]
    if slot == 'coins':
        # 万分之一币是“基础百分之一币 × 整数百分比加成”的最小单位。
        # 旧版百分之一币余数转换一次，不吞掉半枚奖励，也不使用浮点累计。
        prior = remainders.get('coin_units', remainders.get('coins', 0) * 100)
        units = int(Decimal(str(amount)) * 100) * (100 + int(snapshot.get(slot, 0)))
        granted, remainder = divmod(units + prior, 10000)
        if ceiling is not None and granted >= ceiling:
            granted, remainder = ceiling, 0
        remainders['coins'] = 0
        remainders['coin_units'] = remainder
        return granted
    numerator = amount * (100 + int(snapshot.get(slot, 0))) + remainders[slot]
    granted, remainder = divmod(numerator, 100)
    # 每日封顶的超额部分不携带到下一次领取，避免绕过每日上限。
    if ceiling is not None and granted >= ceiling:
        granted, remainder = ceiling, 0
    remainders[slot] = remainder
    return granted


def coin_text(g):
    units = int(g.get('coins', 0)) * 10000 + state(g)['reward_remainders'].get('coin_units', state(g)['reward_remainders'].get('coins', 0) * 100)
    return format(Decimal(units) / 10000, 'f').rstrip('0').rstrip('.') if units % 10000 else str(units // 10000)


def initialize(progress: dict, questions: list[dict], *, legacy: bool, now: float | None = None) -> dict:
    g = progress["game"]
    if isinstance(g.get("product"), dict):
        if g["product"].get("version") not in (1, 2, 3):
            raise ValueError("存档的产品版本暂不支持，请保留原备份。")
        if g["product"]["version"] == 1:
            _upgrade_v2(progress, from_version=1)
        for hero in g['product']['heroes'].values():
            mood.normalize(hero)
        refresh_capacity(g)
        house_state(g)
        return g["product"]
    owned = [identifier for identifier in HEROES if identifier in g.get("inventory", [])] if legacy else []
    if not legacy:
        g["inventory"] = [identifier for identifier in g.get("inventory", []) if identifier not in HEROES]
    s = {"version": 1, "starter_claimed": bool(owned), "heroes": {}, "stock": {}, "transactions": {},
         "daily": {}, "reviews": {}, "chapter_claims": {}, "arena_best": {}, "failures": {},
         "last_active_day": day_key(now), "offline_summary": None,
         "room": {"placements": {}, "wall": {}, "wallpaper": None, "floor": None},
         "settings": {"reduced_motion": False, "sound": True, "volume": 50}, "migration": {"legacy": legacy, "preserved_old_results": True}}
    g["product"] = s
    for identifier in owned:
        s["heroes"][identifier] = {"energy": capacity(g) * 100, "maximum": capacity(g) * 100,
                                  "low_mood": False, "wrong_streak": [], "correct_streak": 0, "rest_started": None}
    g["product_campaign"] = build_routes(questions)
    if legacy:
        for identifier in progress.get("wrong_book", []):
            s["reviews"][identifier] = new_review(timestamp(now), due=0)
        old_levels = g.get("campaign", {}).get("levels", {})
        cleared_questions = {False: set(), True: set()}
        for identifier, result in g.get("results", {}).items():
            if result.get("cleared") and identifier in old_levels:
                old = old_levels[identifier]
                cleared_questions[old["kind"] == "boss"].update(old["qids"])
        for identifier, item in g["product_campaign"]["levels"].items():
            eligible = cleared_questions[item["kind"] == "boss"]
            if set(item["qids"]).issubset(eligible):
                g["results"][identifier] = {"cleared": True, "best_stars": 0, "legacy_migrated": True,
                                            "first_reward_claimed": True, "total": len(item["qids"])}
        for world in g["product_campaign"]["worlds"]:
            for chapter in world["chapters"]:
                if all(g["results"].get(identifier, {}).get("cleared") for identifier in chapter["stages"]):
                    s["chapter_claims"][chapter["id"]] = {"legacy_migrated": True}
    _upgrade_v2(progress, from_version=0 if legacy else None)
    house_state(g)
    return s


def new_review(now: float, *, due: float | None = None) -> dict:
    return {"status": "未纠正", "errors": 1, "phase": 0, "next_due": now + CONFIG["rewards"]["review_answer_cooldown_seconds"] if due is None else due,
            "last_correct": None, "window_start": None, "window_materials": 0, "last_wrong": now}


def login(progress: dict, *, now: float | None = None) -> dict:
    g, today = progress["game"], day_key(now)
    s = state(g)
    previous = s["last_active_day"]
    try:
        elapsed = (date.fromisoformat(today) - date.fromisoformat(previous)).days
    except ValueError as error:
        raise ValueError("存档日期无效，请先恢复备份。") from error
    summary = {"days": 0, "points": 0, "hero": hero_id(g)}
    if elapsed > 0:
        missed = max(0, elapsed - 1)
        if missed and s["starter_claimed"]:
            hero = active_hero(g)
            before = hero["energy"]
            hero["energy"] = max(0, before - missed * CONFIG["energy"]["offline_points_per_day"] * 100)
            summary.update(days=missed, points=(before - hero["energy"]) / 100)
        s["last_active_day"] = today
    s["offline_summary"] = summary
    # 只保留近期每日资格；时间回拨不能回退权威活跃日期。
    keys = sorted(s["daily"])
    for key in keys[:-30]:
        s["daily"].pop(key, None)
    return summary


def claim_starter(progress: dict, identifier: str) -> dict:
    g = progress["game"]
    s = state(g)
    if s["starter_claimed"]:
        raise ValueError("已经领取免费主角，其他伙伴可在商店解锁。")
    if identifier not in HEROES:
        raise ValueError("请选择小圆、小团或小宝。")
    g["inventory"].append(identifier)
    s["heroes"][identifier] = _new_hero(g)
    s["starter_claimed"] = True
    s["starter_hero"] = identifier
    s["entitlements"][identifier] = {"source": "starter"}
    s["appearances"][identifier] = _appearance(identifier)
    switch_hero(progress, identifier)
    return HEROES[identifier]


def switch_hero(progress: dict, identifier: str) -> dict:
    g = progress["game"]
    if identifier != hero_id(g):
        from desktop_hunting import guard
        guard(g)
    if hero_id(g) in state(g)['heroes'] and identifier != hero_id(g) and death_locked(g):
        raise ValueError('体力为0，请先还魂或重新开始，不能切换伙伴绕过。')
    if identifier not in state(g)["heroes"]:
        raise ValueError("这位主角尚未解锁。")
    _sync_appearance(g, identifier)
    refresh_capacity(g)
    return active_hero(g)


def require_action(g: dict) -> None:
    if not state(g)["starter_claimed"]:
        raise ValueError("请先选择免费主角。")
    if death_locked(g):
        raise ValueError("伙伴体力为0，请使用600金币的还魂丹，或重新开始整个游戏。")


def death_locked(g: dict) -> bool:
    s = state(g)
    if not s['starter_claimed']:
        return False
    locked = s.get('death_lock')
    if locked and s['heroes'].get(locked, {}).get('energy', 0) > 0:
        s.pop('death_lock', None)
        locked = None
    if not locked and active_hero(g)['energy'] <= 0:
        s['death_lock'] = hero_id(g)
        locked = hero_id(g)
    return bool(locked)


def spend_energy(g: dict, points: float, *, strict: bool = False) -> float:
    require_action(g)
    hero = active_hero(g)
    amount = int(round(points * 100))
    if strict and hero["energy"] < amount:
        raise ValueError(f"体力不足，需要{points:g}点，请先使用食品。")
    spent = min(hero["energy"], amount)
    hero["energy"] -= spent
    return spent / 100


def daily(g: dict, now: float | None = None) -> dict:
    key = max(day_key(now), state(g)["last_active_day"])
    return state(g)["daily"].setdefault(key, {"answers": {}, "coins": 0, "consolidation_claimed": False, "mood_cost": 0})


def record_action(progress: dict, question: dict, correct: bool, answer: str, attempt: dict,
                  *, mode: str, now: float | None = None, self_assessed: bool = False,
                  energy_points: float | None = None, suppress_mood: bool = False) -> dict:
    g, qid, moment = progress["game"], question["id"], timestamp(now)
    actions = attempt.setdefault("product_actions", {})
    if qid in actions:
        return actions[qid]
    require_action(g)
    hero, day = active_hero(g), daily(g, moment)
    assisted = qid in attempt.get("assisted_qids", []) or qid in attempt.get("hints", {})
    mood_before = mood.normalize(hero)
    spent, extra, mana_extra = 0.0, 0, 0
    if hero["energy"] > 0:
        if not suppress_mood and hero["low_mood"] and not attempt.get("focus_shield"):
            extra = min(int(CONFIG["energy"]["low_mood_extra_points"] * 100),
                        max(0, int(CONFIG["energy"]["low_mood_daily_ceiling"] * 100) - day["mood_cost"]))
        rules=attempt.get('challenge_rules',{})
        base=rules.get('answer_points',CONFIG['energy']['answer_points']) if energy_points is None else energy_points
        penalty=rules.get('wrong_points',0) if not correct and energy_points is None and mode in ('adventure','arena','arena_skills') else 0
        energy_before = hero['energy']
        spent = spend_energy(g, base + penalty + extra / 100)
        extra = max(0, int(round(spent * 100)) - min(energy_before, int(round((base + penalty) * 100))))
        day["mood_cost"] += extra
        if not suppress_mood and hero['low_mood'] and not attempt.get('focus_shield') and hero.get('mana_maximum', 0):
            mana_extra = min(hero.get('mana', 0), CONFIG['mood']['extra_mana'],
                             max(0, CONFIG['mood']['daily_mana_ceiling'] - day.get('mood_mana_cost', 0)))
            hero['mana'] -= mana_extra
            day['mood_mana_cost'] = day.get('mood_mana_cost', 0) + mana_extra
    reward = {"xp": 0, "coins": 0, "materials": 0, "energy": spent, "assisted": assisted,
              "self_assessed": self_assessed, "correct": bool(correct),
              "mood_energy": extra / 100, "mood_mana": mana_extra, "mood_before": mood_before}
    store.record_answer(progress, qid, correct, answer)
    if correct:
        hero["wrong_streak"] = []
        hero["correct_streak"] = hero['correct_streak'] + 1 if not assisted else 0
        mood.change(hero, CONFIG['mood']['correct_gain'] if not assisted else 0)
        if hero["correct_streak"] >= 5:
            mood.set_value(hero, max(mood.value(hero), CONFIG['mood']['rally_floor']))
        if self_assessed and not assisted and qid not in day.setdefault("self_answers", {}):
            reward["xp"] = _reward_with_bonus(g, 2, "xp", attempt.get("bonuses", {}))
            day["self_answers"][qid] = True
        if not self_assessed and not assisted and qid not in day["answers"]:
            reward["xp"] = _reward_with_bonus(g, CONFIG["rewards"]["answer_xp"], "xp", attempt.get("bonuses", {}))
            remainders=state(g)['reward_remainders']
            before_units=remainders.get('coin_units',remainders.get('coins',0)*100)
            reward["coins"] = _reward_with_bonus(g, CONFIG["rewards"]["answer_coins"], "coins", attempt.get("bonuses", {}),
                ceiling=max(0, CONFIG["rewards"]["daily_answer_coins_ceiling"] - day["coins"]))
            credit=Decimal(reward['coins'])+Decimal(remainders.get('coin_units',remainders.get('coins',0)*100)-before_units)/10000
            reward['coin_credit']=format(credit,'f').rstrip('0').rstrip('.') if credit%1 else str(int(credit))
            day["answers"][qid] = True
            day["coins"] += reward["coins"]
            if len(day["answers"]) >= CONFIG["rewards"]["daily_consolidation_questions"] and not day["consolidation_claimed"]:
                reward["materials"] += CONFIG["rewards"]["daily_consolidation_materials"]
                day["consolidation_claimed"] = True
    else:
        hero["correct_streak"] = 0
        if qid not in hero["wrong_streak"]:
            hero["wrong_streak"].append(qid)
            mood.change(hero, -CONFIG['mood']['wrong_loss'])
        if len(hero["wrong_streak"]) >= CONFIG["energy"]["wrong_streak_threshold"]:
            mood.set_value(hero, min(mood.value(hero), CONFIG['mood']['low_threshold']))
        review = state(g)["reviews"].get(qid)
        if review is None:
            state(g)["reviews"][qid] = new_review(moment)
        else:
            review.update(status="未纠正", phase=0, errors=review["errors"] + 1, last_wrong=moment,
                          next_due=moment + CONFIG["rewards"]["review_answer_cooldown_seconds"])
    review = state(g)["reviews"].get(qid)
    if review and review["status"] != "已移出" and correct and mode == "review" and not assisted and moment >= review["next_due"]:
        if review["window_start"] is None or moment - review["window_start"] >= CONFIG["rewards"]["review_reward_window_seconds"]:
            review["window_start"], review["window_materials"] = moment, 0
        phase = min(2, review["phase"] + 1)
        proposed = CONFIG["rewards"]["review_first_materials" if phase == 1 else "review_second_materials"] if review["phase"] < 2 else 0
        granted = min(proposed, max(0, CONFIG["rewards"]["review_window_materials_ceiling"] - review["window_materials"]))
        review["window_materials"] += granted
        review.update(phase=phase, status="待巩固" if phase == 1 else "已掌握", last_correct=moment,
                      next_due=moment + (CONFIG["rewards"]["review_second_gap_seconds"] if phase == 1 else 3 * 86400),
                      self_assessed=self_assessed)
        reward["materials"] += granted
        reward["review_phase"] = phase
    if review and review["status"] not in ("已掌握", "已移出") and qid not in progress["wrong_book"]:
        progress["wrong_book"].append(qid)
    reward['mood_after'] = mood.value(hero)
    g["xp"] += reward["xp"]
    g["coins"] += reward["coins"]
    add_materials(g, reward["materials"])
    refresh_capacity(g)
    feedback = pick_feedback(g, correct, review=mode == "review" and reward["materials"] > 0,
                             previous=state(g).get("last_feedback_pose"))
    reward["feedback"] = feedback
    state(g)["last_feedback_pose"] = feedback["pose"]
    actions[qid] = reward
    state(g)["last_active_day"] = max(state(g)["last_active_day"], day_key(moment))
    return reward


def ordered_stages(g: dict, world_id: str) -> list[str]:
    world = next(world for world in g["product_campaign"]["worlds"] if world["id"] == world_id)
    return [identifier for chapter in world["chapters"] for identifier in chapter["stages"]]


def can_play(g: dict, identifier: str) -> bool:
    item = g["product_campaign"]["levels"][identifier]
    sequence = ordered_stages(g, item["world_id"])
    index = sequence.index(identifier)
    return index == 0 or bool(g["results"].get(sequence[index - 1], {}).get("cleared"))


def next_stage(g: dict, identifier: str | None = None, world_id: str | None = None) -> str | None:
    world_id = world_id or (g["product_campaign"]["levels"][identifier]["world_id"] if identifier else g["world"])
    sequence = ordered_stages(g, world_id)
    if identifier:
        index = sequence.index(identifier) + 1
        return sequence[index] if index < len(sequence) else None
    return next((key for key in sequence if not g["results"].get(key, {}).get("cleared")), sequence[-1] if sequence else None)


def start_adventure(progress: dict, identifier: str, *, restart: bool = False) -> dict:
    g = progress["game"]
    require_action(g)
    if not can_play(g, identifier):
        raise ValueError("请先完成前一个关卡。")
    current = g.get("active")
    if current and current["stage_id"] == identifier and not current["settled"] and not restart:
        return current
    if current and not current["settled"]:
        g["paused"][current["stage_id"]] = current
    saved = g["paused"].pop(identifier, None)
    if saved and not restart:
        g["active"] = saved
        return saved
    item = g["product_campaign"]["levels"][identifier]
    attempt = {"id": uuid.uuid4().hex, "stage_id": identifier, "qids": list(item["qids"]),
               "answers": {}, "drafts": {}, "references": [], "index": 0, "settled": False,
               "result": None, "bonuses": bonuses(g), "product_mode": "adventure"}
    g["active"] = attempt
    return attempt


def submit_adventure(progress: dict, question: dict, answer: str, correct: bool) -> bool:
    attempt = progress["game"]["active"]
    if not attempt or attempt["settled"] or question["id"] not in attempt["qids"]:
        raise ValueError("题目不属于进行中的挑战。")
    if question["id"] in attempt["answers"]:
        return False
    if not answer.strip():
        raise ValueError("请先作答。")
    if store.is_subjective(question) and question["id"] not in attempt["references"]:
        raise ValueError("请先查看参考答案，再对照自评。")
    reward = record_action(progress, question, correct, answer, attempt, mode="adventure", self_assessed=store.is_subjective(question))
    attempt["answers"][question["id"]] = {"correct": bool(correct), "user_answer": answer,
        "ts": timestamp(), "assisted": reward["assisted"], "self_assessed": reward["self_assessed"]}
    return True


def early_end_status(attempt):
    if not attempt or attempt.get('product_mode') != 'adventure' or not str(attempt.get('stage_id', '')).startswith('v5:'):
        return {'allowed': False, 'reason': '只有冒险关卡可提前结束。'}
    qids, answers = attempt['qids'], attempt.get('answers', {})
    required = math.ceil(len(qids) * attempt.get('challenge_rules', {}).get('pass_percent', CONFIG['pass_percent']) / 100)
    judged = [qid for qid in qids if qid in answers]
    correct = sum(bool(answers[qid].get('game_correct', answers[qid].get('correct'))) for qid in judged)
    unjudged = len(qids) - len(judged)
    maximum = correct + unjudged
    allowed = not attempt.get('settled') and maximum < required
    return {'allowed': allowed, 'required': required, 'maximum': maximum, 'unjudged': unjudged,
            'reason': f'剩余全对也最多 {maximum} 题，通关需要 {required} 题。' if allowed else '还有机会达到通关线，请继续作答。'}


def end_adventure_early(progress):
    attempt = progress['game'].get('active')
    if attempt and attempt.get('settled') and attempt.get('early_end'):
        return attempt['result']
    status = early_end_status(attempt)
    if not status['allowed']:
        raise ValueError(status['reason'])
    attempt['early_end'] = True
    attempt['early_end_status'] = status
    return settle_adventure(progress)


def settle_adventure(progress: dict) -> dict:
    g, attempt = progress["game"], progress["game"]["active"]
    if attempt["settled"]:
        return attempt["result"]
    if not attempt.get('early_end'):
        require_action(g)
    missing = [qid for qid in attempt['qids'] if qid not in attempt['answers']]
    if missing and not (attempt.get('early_end') and early_end_status(attempt)['allowed']):
        raise ValueError("请完成全部题目后结算。")
    item = g["product_campaign"]["levels"][attempt["stage_id"]]
    total = len(attempt["qids"])
    correct = sum(bool(attempt['answers'].get(qid, {}).get('correct')) for qid in attempt['qids'])
    wrong = [qid for qid in attempt['qids'] if qid in attempt['answers'] and not attempt['answers'][qid]['correct']]
    assisted = any(rec.get("assisted") for rec in attempt["answers"].values())
    rule=attempt.get('challenge_rules',{})
    strict_boss = bool(rule.get('boss') and rule.get('version') != '5.4.1')
    passed = correct * 100 >= total * rule.get('pass_percent',CONFIG["pass_percent"]) or (bool(attempt.get("remediation_completed")) and not strict_boss)
    if attempt.get('early_end'):
        passed = False
    self_assessed = any(rec.get("self_assessed") for rec in attempt["answers"].values())
    stars = (1 if attempt.get("remediation_completed") or self_assessed else 3 if correct == total and not assisted else 2) if passed else 0
    previous = g["results"].get(item["id"], {})
    first = passed and not previous.get("cleared")
    before = level(g)
    hero = active_hero(g)
    mood_before = mood.value(hero)
    reward = CONFIG["rewards"]
    xp, coins, building = (rule.get('first_stage_xp',reward["first_stage_xp"]),rule.get('first_stage_coins',reward["first_stage_coins"]),0) if first else (0,0,0)
    if passed:
        g["results"][item["id"]] = {**previous, "cleared": True, "best_stars": max(stars, previous.get("best_stars", 0)),
            "total": total, "best_correct": max(correct, previous.get("best_correct", 0)),
            "first_reward_claimed": True, "latest_first_correct": correct}
        chapter = next(ch for world in g["product_campaign"]["worlds"] for ch in world["chapters"] if ch["id"] == item["chapter_id"])
        if chapter["id"] not in state(g)["chapter_claims"] and all(g["results"].get(key, {}).get("cleared") for key in chapter["stages"]):
            xp += reward["first_chapter_xp"]
            coins += reward["first_chapter_coins"]
            building += reward["first_chapter_materials"]
            state(g)["chapter_claims"][chapter["id"]] = {"attempt_id": attempt["id"]}
        state(g)["failures"].pop(item["id"], None)
    else:
        count = state(g)["failures"].get(item["id"], 0) + 1
        state(g)["failures"][item["id"]] = count
        if count >= CONFIG["energy"]["stage_failure_threshold"]:
            mood.set_value(active_hero(g), min(mood.value(active_hero(g)), CONFIG['mood']['low_threshold']))
    if passed:
        mood.recover(hero, CONFIG['mood'].get('stage_clear_gain', 0))
    else:
        mood.change(hero, -CONFIG['mood'].get('stage_failure_loss', 0))
    xp = _reward_with_bonus(g, xp, "xp", attempt.get("bonuses", {}))
    coins = _reward_with_bonus(g, coins, "coins", attempt.get("bonuses", {}))
    g["xp"] += xp
    g["coins"] += coins
    add_materials(g, building)
    refresh_capacity(g)
    result = {"attempt_id": attempt["id"], "stage_id": item["id"], "correct": correct, "total": total,
              "passed": passed, "stars": stars, "first_clear": first, "xp": xp, "coins": coins,
              "materials": building, "wrong_qids": wrong, "assisted": assisted,
              "self_assessed": self_assessed, "level_before": before,
              "level_after": level(g), "remediation": bool(attempt.get("remediation_completed"))}
    result.update(early_end=bool(attempt.get('early_end')), answered=total - len(missing), unjudged=len(missing))
    result.update(mood_before=mood_before, mood_after=mood.value(hero), mood_change=mood.value(hero)-mood_before)
    attempt.update(settled=True, result=result)
    g["last_result"] = result
    return result


def finish_remediation(progress: dict, parent_attempt_id: str, corrected: list[str]) -> dict:
    g, a = progress["game"], progress["game"]["active"]
    if a["id"] != parent_attempt_id or not a["settled"] or a["result"]["passed"]:
        raise ValueError("补练所属关卡已经改变，请返回地图继续。")
    if a.get('early_end'):
        raise ValueError('提前结束后请重新挑战完整关卡；未答题目不会记入错题本。')
    if set(a["result"]["wrong_qids"]) - set(corrected):
        raise ValueError("请独立答对全部补练题。")
    if a.get('challenge_rules', {}).get('boss') and a['challenge_rules'].get('version') != '5.4.1':
        # 复盘只补齐学习记录，Boss仍须在一次完整挑战达到90%。
        a['remediation_completed'] = True
        a['result']['requires_boss_retry'] = True
        return a['result']
    a["remediation_completed"], a["settled"] = True, False
    return settle_adventure(progress)


def start_practice(progress: dict, qids: list[str], *, mode: str, name: str, target: int = 0,
                   chapter_key: str = "", parent_attempt_id: str | None = None) -> dict:
    g = progress["game"]
    require_action(g)
    if not qids or len(qids) != len(set(qids)):
        raise ValueError("请先选择有效且不重复的练习题。")
    if mode not in ("basic", "review", "arena", "remediation"):
        raise ValueError("练习模式无效。")
    if mode == "remediation":
        parent = g.get("active")
        if not parent or parent["id"] != parent_attempt_id or not parent["settled"] or parent["result"]["passed"]:
            raise ValueError("补练所属关卡已经改变，请返回地图继续。")
        if not set(qids).issubset(parent["result"]["wrong_qids"]):
            raise ValueError("补练只能选择本关首答错题。")
    a = {"id": "product-practice-" + uuid.uuid4().hex, "qids": list(qids), "name": name,
         "answers": {}, "drafts": {}, "references": [], "index": 0, "settled": False,
         "product_mode": mode, "target": target, "chapter_key": chapter_key,
         "parent_attempt_id": parent_attempt_id, "bonuses": bonuses(g)}
    progress["practice"] = a
    return a


def submit_practice(progress: dict, question: dict, answer: str, correct: bool, *, now: float | None = None) -> dict:
    a = progress.get("practice")
    if not a or a["settled"] or question["id"] not in a["qids"]:
        raise ValueError("题目不属于当前练习。")
    if question["id"] in a["answers"]:
        return a["product_actions"][question["id"]]
    if not answer.strip():
        raise ValueError("请先作答。")
    if store.is_subjective(question) and question["id"] not in a["references"]:
        raise ValueError("请先查看参考答案，再对照自评。")
    reward = record_action(progress, question, correct, answer, a, mode=a["product_mode"], now=now,
                           self_assessed=store.is_subjective(question))
    a["answers"][question["id"]] = {"correct": bool(correct), "user_answer": answer,
        "ts": timestamp(now), "assisted": reward["assisted"], "self_assessed": reward["self_assessed"]}
    return reward


def settle_practice(progress: dict, *, now: float | None = None) -> dict:
    g, a = progress["game"], progress["practice"]
    if a["settled"]:
        return a["result"]
    require_action(g)
    if any(qid not in a["answers"] for qid in a["qids"]):
        raise ValueError("请完成本场全部题目。")
    actual_correct = sum(bool(rec["correct"]) for rec in a["answers"].values())
    independent_correct = sum(bool(rec["correct"]) and not rec.get("assisted") and not rec.get("self_assessed")
                              for rec in a["answers"].values())
    earned, outcome = 0, None
    if a["product_mode"] == "arena":
        outcome = "胜" if independent_correct > a["target"] else "平" if independent_correct == a["target"] else "败"
        key = max(day_key(now), state(g)["last_active_day"]) + ":" + a["chapter_key"]
        proposed = CONFIG["rewards"]["arena_xp"][outcome]
        previous = state(g)["arena_best"].get(key, 0)
        earned = _reward_with_bonus(g, max(0, proposed - previous), "xp", a.get("bonuses", {}))
        state(g)["arena_best"][key] = max(previous, proposed)
        g["xp"] += earned
        refresh_capacity(g)
    result = {"mode": a["product_mode"], "name": a["name"], "correct": actual_correct,
              "independent_correct": independent_correct,
              "self_assessed": any(rec.get("self_assessed") for rec in a["answers"].values()), "total": len(a["qids"]),
              "outcome": outcome, "target": a["target"], "xp": earned,
              "wrong_qids": [qid for qid, rec in a["answers"].items() if not rec["correct"]]}
    if a["product_mode"] == "remediation":
        corrected = [qid for qid, rec in a["answers"].items() if rec["correct"] and not rec.get("assisted")]
        parent = g.get("active")
        if not parent or parent["id"] != a["parent_attempt_id"]:
            raise ValueError("补练所属关卡已经改变，请返回地图继续。")
        accumulated = set(parent.get("remediation_corrected", [])) | set(corrected)
        parent["remediation_corrected"] = sorted(accumulated)
        remaining = [qid for qid in parent["result"]["wrong_qids"] if qid not in accumulated]
        if not remaining:
            result["adventure_result"] = finish_remediation(progress, a["parent_attempt_id"], list(accumulated))
        else:
            result["remediation_remaining"] = remaining
    a.update(settled=True, result=result)
    return result


def use_skill(progress: dict, identifier: str, question: dict, *, practice: bool) -> str:
    g = progress["game"]
    a = progress.get("practice") if practice else g.get("active")
    if not a or a["settled"] or question["id"] not in a["qids"] or question["id"] in a["answers"]:
        raise ValueError("请在尚未提交的题目上使用技能。")
    definition = SKILLS[identifier]
    if level(g) < definition["level"]:
        raise ValueError(f"技能在Lv.{definition['level']}开放。")
    key = identifier + (":" + question["id"] if identifier == "recall" else "")
    if key in a.get("product_skills", []):
        raise ValueError("本题或本场已经使用过这个技能。")
    if identifier == "rally" and not active_hero(g)["low_mood"]:
        raise ValueError("伙伴当前没有低落状态。")
    spend_energy(g, definition["energy"], strict=True)
    a.setdefault("product_skills", []).append(key)
    if identifier == "recall":
        a.setdefault("assisted_qids", []).append(question["id"])
        clue = " · ".join(str(v) for v in (question.get("chapter"), question.get("knowledge_point") or question.get("topic"), question.get("type")) if v)
        a.setdefault("product_clues", {})[question["id"]] = clue
        return "回忆线索：" + clue
    if identifier == "focus":
        a["focus_shield"] = True
        return "专注结界已开启，本场免除低落额外消耗。"
    mood.recover(active_hero(g), 0, floor=CONFIG['mood']['rally_floor'])
    return "伙伴重新振作起来，当前体力没有增加。"


def buy(progress: dict, identifier: str, transaction_id: str) -> dict:
    g, s = progress["game"], state(progress["game"])
    prior = s["transactions"].get(transaction_id)
    if prior:
        if prior.get("operation") != "buy" or prior.get("item") != identifier:
            raise ValueError("交易编号与操作不一致。")
        return prior["result"]
    status = purchase_status(g, identifier)
    if not status["allowed"]:
        raise ValueError(status["reason"])
    item = SHOP_CATALOG[identifier]
    currency = item["currency"]
    if currency == "coins":
        g["coins"] -= item["price"]
    else:
        add_materials(g, -item["price"])
    if identifier in HEROES:
        g["inventory"].append(identifier)
        archived = s["archived_heroes"].pop(identifier, None)
        s["heroes"][identifier] = archived["state"] if archived else _new_hero(g)
        s["appearances"][identifier] = archived["appearance"] if archived else _appearance(identifier)
        s["entitlements"][identifier] = {"source": "purchase", "transaction_id": transaction_id}
        refresh_capacity(g)
    elif item["category"] == "装备":
        g["inventory"].append(identifier)
    elif item["kind"] == "floor_upgrade":
        house = house_state(g)
        floor = item["target_floor"]
        house["floors"][str(floor)] = {"placements": {}, "wall": {}, "wallpaper": None, "floor": None}
        house["unlocked_floors"] = floor
        s["stock"][identifier] = 1
    else:
        s["stock"][identifier] = s["stock"].get(identifier, 0) + 1
    result = {"item": identifier, "price": item["price"], "currency": currency, "operation": "buy", "owned": owned_count(g, identifier)}
    s["transactions"][transaction_id] = {"operation": "buy", "item": identifier, "result": result}
    return result


def _target_hero(g: dict, identifier: str | None) -> str:
    target = identifier or hero_id(g)
    if target not in state(g)["heroes"]:
        raise ValueError("目标主角尚未解锁。")
    return target


def equip(progress: dict, identifier: str, transaction_id: str, hero_id: str | None = None) -> dict:
    g, s = progress["game"], state(progress["game"])
    item = SHOP_CATALOG.get(identifier)
    if item is None:
        raise ValueError("这件物品不能通过装备栏穿戴。")
    target = item["id"] if item["kind"] == "hero" else hero_id or item.get("fit_character") or _current_hero_id(g)
    prior = s["transactions"].get(transaction_id)
    if prior:
        if prior.get("operation") != "equip" or prior.get("item") != identifier or prior.get("hero") != target:
            raise ValueError("交易编号与操作或目标角色不一致。")
        return prior["result"]
    _target_hero(g, target)
    if not owned_count(g, identifier):
        raise ValueError("尚未拥有这件物品。")
    if item.get("fit_character") and item["fit_character"] != target:
        raise ValueError("这套服装不适合所选主角。")
    slot = item["slot"]
    if item["kind"] == "hero":
        switch_hero(progress, identifier)
    elif slot in PERSONAL_SLOTS:
        s["appearances"][target][slot] = identifier
        if _current_hero_id(g) == target:
            _sync_appearance(g, target)
    elif slot in ("xp", "coins", "wonder"):
        g["equipment"][slot] = identifier
    else:
        raise ValueError("这件物品没有可穿戴的装备槽。")
    refresh_capacity(g)
    result = {"hero": target, "item": identifier, "operation": "equip", "slot": slot, "bonuses": bonuses(g)}
    s["transactions"][transaction_id] = {"operation": "equip", "item": identifier, "hero": target, "result": result}
    return result


def unequip(progress: dict, slot: str, transaction_id: str, hero_id: str | None = None) -> dict:
    g, s = progress["game"], state(progress["game"])
    target = hero_id or _current_hero_id(g)
    prior = s["transactions"].get(transaction_id)
    if prior:
        if prior.get("operation") != "unequip" or prior.get("slot") != slot or prior.get("hero") != target:
            raise ValueError("交易编号与操作或目标角色不一致。")
        return prior["result"]
    _target_hero(g, target)
    if slot not in SLOTS:
        raise ValueError("装备槽无效。")
    slots = s["appearances"][target] if slot in PERSONAL_SLOTS else g["equipment"]
    previous = slots.get(slot)
    slots[slot] = None
    if slot in PERSONAL_SLOTS and _current_hero_id(g) == target:
        _sync_appearance(g, target)
    refresh_capacity(g)
    result = {"hero": target, "item": previous, "operation": "unequip", "slot": slot, "bonuses": bonuses(g)}
    s["transactions"][transaction_id] = {"operation": "unequip", "slot": slot, "hero": target, "result": result}
    return result


def consumption_preview(g: dict, identifier: str, hero_id: str | None = None) -> dict:
    if identifier not in CATALOG:
        raise ValueError("这件物品不能作为消耗品使用。")
    target = _target_hero(g, hero_id)
    item, hero = CATALOG[identifier], state(g)["heroes"][target]
    if item["category"] != "消耗品":
        raise ValueError("这件物品不能作为消耗品使用。")
    if item["kind"] == "revive":
        if hero["energy"] > 0:
            raise ValueError("还魂丹只用于体力为0的休眠伙伴。")
        requested = hero["maximum"] * item["restore_percent"] // 100
    elif hero["energy"] <= 0:
        raise ValueError("休眠伙伴必须先使用还魂丹，普通食品和暖心饮不能唤醒。")
    elif item['kind'] == 'mana':
        require_action(g)
        if not growth.mana_maximum(g, target):
            raise ValueError('十级学习技能后才开启魔法和补蓝。')
        maximum = growth.mana_maximum(g, target)
        if hero['mana'] >= maximum:
            raise ValueError('魔法已满，不必浪费药品。')
        requested = item['restore_mana']
        gain = min(requested, maximum - hero['mana'])
        return {'before': hero['mana'], 'after': hero['mana'] + gain, 'gain': gain,
                'overflow': requested - gain, 'hero': target, 'resource': 'mana'}
    elif item["kind"] == "calm":
        before = mood.value(hero)
        if before >= CONFIG['mood']['maximum']:
            raise ValueError("心情已满，无需使用这件恢复用品。")
        requested = item.get('restore_mood', CONFIG['mood']['calm_restore'])
        after = min(CONFIG['mood']['maximum'], before + requested)
        return {'before': before, 'after': after, 'gain': after - before,
                'overflow': requested - (after - before), 'hero': target, 'resource': 'mood'}
    else:
        if hero["energy"] >= hero["maximum"]:
            raise ValueError("体力已经充足，不必浪费食品。")
        requested = int(item.get("restore_points", 0) * 100) or hero["maximum"] * item.get("restore_percent", 0) // 100
    gain = min(requested, hero["maximum"] - hero["energy"])
    return {"before": hero["energy"] / 100, "after": (hero["energy"] + gain) / 100,
            "gain": gain / 100, "overflow": (requested - gain) / 100, "hero": target}


def consume(progress: dict, identifier: str, transaction_id: str, hero_id: str | None = None) -> dict:
    g, s = progress["game"], state(progress["game"])
    target = hero_id or _current_hero_id(g)
    prior = s["transactions"].get(transaction_id)
    if prior:
        if prior.get("operation") != "consume" or prior.get("item") != identifier or prior.get("hero", prior.get("result", {}).get("hero")) != target:
            raise ValueError("交易编号与操作或目标角色不一致。")
        return prior["result"]
    if s["stock"].get(identifier, 0) <= 0:
        raise ValueError("背包里没有这件消耗品，请先购买。")
    preview = consumption_preview(g, identifier, target)
    hero = s["heroes"][target]
    if preview.get('resource') == 'mood':
        mood.recover(hero, int(preview['gain']))
    elif preview.get('resource') == 'mana':
        hero['mana'] = int(preview['after'])
    else:
        hero["energy"] = int(round(preview["after"] * 100))
    if CATALOG[identifier]["kind"] == 'revive':
        mood.recover(hero, 0, floor=CONFIG['mood']['revive_floor'])
    if CATALOG[identifier]['kind'] == 'revive' and s.get('death_lock') == target:
        s.pop('death_lock', None)
    s["stock"][identifier] -= 1
    s["transactions"][transaction_id] = {"operation": "consume", "item": identifier, "hero": target, "result": preview}
    return preview


def rest(progress: dict, *, now: float | None = None) -> dict:
    hero = active_hero(progress["game"])
    moment = timestamp(now)
    if hero["rest_started"] is None:
        hero["rest_started"] = moment
    ready = moment - hero["rest_started"] >= CONFIG["energy"]["calm_rest_seconds"]
    if ready:
        restored = mood.recover(hero, CONFIG['mood']['rest_restore'], floor=CONFIG['mood']['rally_floor'])
        hero["rest_started"] = None
    return {"ready": ready, "mood": mood.value(hero), 'mood_gain': restored['change'] if ready else 0,
            "remaining": max(0, CONFIG["energy"]["calm_rest_seconds"] - (moment - (hero["rest_started"] if hero['rest_started'] is not None else moment))) if not ready else 0}


def placed_count(g: dict, identifier: str) -> int:
    rooms = house_state(g)["floors"].values()
    return sum(sum(v["item"] == identifier for v in room["placements"].values()) + sum(v == identifier for v in room["wall"].values()) for room in rooms)


def place(progress: dict, identifier: str, *, x: int = 0, y: int = 0, slot: str = "center", instance: str | None = None) -> dict:
    g, item = progress["game"], CATALOG[identifier]
    s, room = state(g), state(g)["room"]
    if s["stock"].get(identifier, 0) <= 0:
        raise ValueError("尚未拥有这件家装物品。")
    if item["kind"] in ("wallpaper", "floor"):
        room[item["kind"]] = identifier
        return {"item": identifier}
    if item["kind"] == "wall":
        if slot not in CONFIG["room"]["wall_slots"]:
            raise ValueError("窗户和挂画只能装在墙面槽位。")
        if room["wall"].get(slot) == identifier:
            return {"item": identifier, "slot": slot}
        if placed_count(g, identifier) >= s["stock"][identifier]:
            raise ValueError("背包中没有尚未放置的同款物品，请先收回。")
        room["wall"][slot] = identifier
        return {"item": identifier, "slot": slot}
    if item["kind"] != "furniture":
        raise ValueError("这件物品不能放入房间。")
    if instance and (instance not in room["placements"] or room["placements"][instance]["item"] != identifier):
        raise ValueError("要移动的家具不存在。")
    if not instance and placed_count(g, identifier) >= s["stock"][identifier]:
        raise ValueError("这件家具已经全部放入房间，可选择移动或收回。")
    if not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0 or x + item["width"] > CONFIG["room"]["columns"] or y + item["height"] > CONFIG["room"]["rows"]:
        raise ValueError("家具超出房间范围。")
    occupied = {(col, row) for key, placed in room["placements"].items() if key != instance
                and placed.get('item') in CATALOG
                for col in range(placed["x"], placed["x"] + CATALOG[placed["item"]]["width"])
                for row in range(placed["y"], placed["y"] + CATALOG[placed["item"]]["height"])}
    if any((col, row) in occupied for col in range(x, x + item["width"]) for row in range(y, y + item["height"])):
        raise ValueError("这个位置已有家具，请换一处。")
    instance = instance or uuid.uuid4().hex
    room["placements"][instance] = {"item": identifier, "x": x, "y": y}
    return {"instance": instance, **room["placements"][instance]}


def remove_placement(progress: dict, instance: str) -> None:
    room = state(progress["game"])["room"]
    if instance in CONFIG["room"]["wall_slots"]:
        room["wall"].pop(instance, None)
    else:
        room["placements"].pop(instance, None)


def review_queue(g: dict, qmap: dict, *, due_only: bool = True, now: float | None = None) -> list[str]:
    moment = timestamp(now)
    items = [(qid, rec) for qid, rec in state(g)["reviews"].items() if qid in qmap and rec["status"] not in ("已掌握", "已移出")
             and (not due_only or rec["next_due"] <= moment)]
    return [qid for qid, _ in sorted(items, key=lambda item: (item[1]["next_due"], item[0]))]


def pick_feedback(g: dict, correct: bool, *, review: bool = False, previous: str | None = None,
                  rng=None) -> dict:
    rng = rng or random.SystemRandom()
    pool = CONFIG["feedback"]["correct" if correct else "wrong"]
    choices = [pose for pose in pool if pose != previous]
    pose = rng.choice(choices or pool)
    texts = CONFIG["feedback"]["review_text" if correct and review else "correct_text" if correct else "wrong_text"]
    return {"pose": pose, "text": rng.choice(texts)}


# 旧场次保留5.1规则；新场次统一使用5.2成长规则。
import desktop_growth as growth

_legacy_level = level
_legacy_capacity = capacity
_legacy_initialize = initialize
_legacy_login = login
_legacy_claim_starter = claim_starter
_legacy_buy = buy
_legacy_record_action = record_action
_legacy_start_adventure = start_adventure
_legacy_start_practice = start_practice
_legacy_submit_adventure = submit_adventure
_legacy_submit_practice = submit_practice
_legacy_settle_adventure = settle_adventure
_legacy_settle_practice = settle_practice
_legacy_use_skill = use_skill


def level(g):
    return growth.level(g) if growth.enabled(g) else _legacy_level(g)


def capacity(g):
    if not growth.enabled(g):
        return _legacy_capacity(g)
    rule = CONFIG['energy']
    return min(rule['capacity_ceiling'], rule['initial_points']+rule['level_capacity_points']*level(g))


def initialize(progress, questions, *, legacy, now=None):
    g = progress['game']
    previous = g.get('product')
    if previous and g.get('product_campaign',{}).get('version')==2:
        from supplement_migration import references,product as migrate_product
        references(progress)
        g=progress['game'];previous=g.get('product')
        migrate_product(progress,[q for q in questions if not q.get('book_id','').startswith('cpa_sj_')])
    from audit_migration import product as append_audit
    append_audit(progress,questions)
    fresh = not legacy and previous is None
    xp = max(0,int(g.get('xp',0)))
    # 即便来自更早的存档，也按5.1主界面曲线保护；不再套技能页500经验曲线。
    old_lv = _legacy_level(g) if not fresh else 0
    old_start = 100*(old_lv-1) if old_lv<=5 else 400+200*(old_lv-5)
    old_fraction = (xp-old_start)/(100 if old_lv<5 else 200) if not fresh else 0
    s = _legacy_initialize(progress,questions,legacy=legacy,now=now)
    growth.migrate(progress,fresh=fresh,old_level=old_lv,old_fraction=max(0,min(old_fraction,.999999)),now=now)
    s.setdefault('onboarding', {'stage': 'ready' if s['starter_claimed'] else 'welcome', 'selected': None})
    for appearance in s['appearances'].values():
        for slot in PERSONAL_SLOTS:
            appearance.setdefault(slot, None)
    for a in [g.get('active'), progress.get('practice'), *g.get('paused', {}).values()]:
        if a and not a.get('settled'):
            growth.upgrade_attempt(g, a)
    from finance import initialize_companions
    initialize_companions(g)
    refresh_capacity(g)
    from desktop_hunting import initialize as initialize_hunting
    initialize_hunting(g)
    return s


def login(progress, *, now=None):
    return growth.login(progress,now=now) if growth.enabled(progress['game']) else _legacy_login(progress,now=now)


def claim_starter(progress, identifier):
    result = _legacy_claim_starter(progress,identifier)
    if growth.enabled(progress['game']):
        growth.enroll(progress['game'],identifier)
    state(progress['game'])['onboarding'] = {'stage': 'ready', 'selected': identifier}
    refresh_capacity(progress['game'])
    return result


def begin_onboarding(progress):
    s = state(progress['game'])
    if not s['starter_claimed']:
        s['onboarding']['stage'] = 'choosing'
    return s['onboarding']


def preselect_starter(progress, identifier):
    s = state(progress['game'])
    if s['starter_claimed'] or s['onboarding']['stage'] != 'choosing' or identifier not in HEROES:
        raise ValueError('请从欢迎页开始，再预选有效主角。')
    s['onboarding']['selected'] = identifier
    return identifier


def buy(progress, identifier, transaction_id, *args, **kwargs):
    if identifier in HEROES and not state(progress['game'])['transactions'].get(transaction_id):
        raise ValueError('主角请到角色馆参加100题收服考试，不能直接购买。')
    result = _legacy_buy(progress,identifier,transaction_id,*args,**kwargs)
    if growth.enabled(progress['game']) and identifier in HEROES:
        growth.enroll(progress['game'],identifier)
    return result


def start_adventure(progress, stage_id, *, restart=False):
    from desktop_hunting import guard
    guard(progress['game'])
    a = _legacy_start_adventure(progress,stage_id,restart=restart)
    import world_scenes
    a.setdefault('scene_id',world_scenes.stage_scene(progress['game'],stage_id))
    if growth.enabled(progress['game']):
        growth.upgrade_attempt(progress['game'],a)
    return a


def start_practice(progress, qids, *, mode, name, target=0, chapter_key='', parent_attempt_id=None):
    from desktop_hunting import guard
    guard(progress['game'])
    if mode in ('arena','arena_skills'):
        from desktop_challenge import validate_arena
        validate_arena(qids)
    if mode=='arena_skills' and (not growth.enabled(progress['game']) or level(progress['game'])<10):
        raise ValueError('技能比武在10级开放。')
    a = _legacy_start_practice(progress,qids,mode='arena' if mode=='arena_skills' else mode,name=name,
                               target=target,chapter_key=chapter_key,parent_attempt_id=parent_attempt_id)
    a['product_mode'] = mode
    from desktop_challenge import question_map
    import world_scenes
    first_question = question_map().get(qids[0])
    if first_question:
        a['scene_id'] = world_scenes.question_scene(first_question)
    if growth.enabled(progress['game']):
        growth.prepare(progress['game'],a)
    return a


def record_action(progress, question, correct, answer, attempt, *, mode, now=None, self_assessed=False):
    from desktop_hunting import guard
    guard(progress['game'])
    require_action(progress['game'])
    if growth.current(attempt):
        return growth.record_action(progress,question,correct,answer,attempt,mode=mode,now=now,
                                     self_assessed=self_assessed,legacy=_legacy_record_action)
    result = _legacy_record_action(progress,question,correct,answer,attempt,mode=mode,now=now,self_assessed=self_assessed)
    if growth.enabled(progress['game']):
        growth.login(progress,now=now)
        growth.activity(progress['game'],question['id'],growth.state(progress['game'])['last_seen_day'])
    return result


def submit_adventure(progress, question, answer, correct):
    a = progress['game']['active']
    if growth.current(a) and store.is_subjective(question) and question['id'] in a.get('primary_submissions',{}):
        answer = a['primary_submissions'][question['id']]['draft']
    result = _legacy_submit_adventure(progress,question,answer,correct)
    a = progress['game']['active']
    if growth.current(a) and question['id'] in a['answers']:
        growth.stamp_answer(a,question['id'])
    return result


def submit_practice(progress, question, answer, correct, *, now=None):
    a = progress['practice']
    if growth.current(a) and store.is_subjective(question) and question['id'] in a.get('primary_submissions',{}):
        answer = a['primary_submissions'][question['id']]['draft']
    result = _legacy_submit_practice(progress,question,answer,correct,now=now)
    a = progress['practice']
    if growth.current(a):
        growth.stamp_answer(a,question['id'])
    return result


def settle_adventure(progress):
    a, g = progress['game']['active'], progress['game']
    if not growth.current(a) or a['settled']:
        return _legacy_settle_adventure(progress)
    actual = {qid:(r['correct'],r.get('assisted',False)) for qid,r in a['answers'].items()}
    previous_best = g['results'].get(a['stage_id'],{}).get('best_correct',0)
    try:
        for r in a['answers'].values():
            r['correct'] = r.get('game_correct',r['correct'])
            r['assisted'] = r.get('assisted',False) or r.get('protected',False)
        result = _legacy_settle_adventure(progress)
    finally:
        for qid,(correct,assisted) in actual.items():
            a['answers'][qid].update(correct=correct,assisted=assisted)
    if a['stage_id'] in g['results']:
        raw = sum(bool(r['correct']) for r in a['answers'].values())
        g['results'][a['stage_id']].update(best_correct=max(previous_best,raw),latest_first_correct=raw,
                                         best_game_correct=result['correct'])
    return growth.finish(progress,a,result)


def settle_practice(progress, *, now=None):
    a = progress['practice']
    if not growth.current(a) or a['settled']:
        return _legacy_settle_practice(progress,now=now)
    skill_mode = a['product_mode']=='arena_skills'
    actual = {qid:(r['correct'],r.get('assisted',False)) for qid,r in a['answers'].items()}
    if skill_mode:
        a['product_mode']='arena'
        for r in a['answers'].values():
            r.update(correct=r.get('game_correct',r['correct']),assisted=False)
    try:
        result = _legacy_settle_practice(progress,now=now)
    finally:
        if skill_mode:
            a['product_mode']='arena_skills'
            for qid,(correct,assisted) in actual.items():
                a['answers'][qid].update(correct=correct,assisted=assisted)
    result['mode']=a['product_mode']
    result['independent_correct']=sum(bool(r['correct']) and not r.get('assisted') and not r.get('self_assessed') for r in a['answers'].values())
    return growth.finish(progress,a,result)


def use_skill(progress, identifier, question, *, practice):
    from desktop_hunting import guard
    guard(progress['game'])
    require_action(progress['game'])
    a = progress.get('practice') if practice else progress['game'].get('active')
    if growth.current(a):
        return growth.use(progress,a,question,identifier)
    return _legacy_use_skill(progress,identifier,question,practice=practice)
