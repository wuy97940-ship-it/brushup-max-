"""商店展示与试穿副本；与手机共用奇物、价格、技能配置。"""
from __future__ import annotations

import copy

import game
import game_skills as skills
import finance

CATEGORIES = {"all": "全部", "characters": "伙伴", "outfits": "换装", "equipment": "装备",
              "collection": "收藏", "skills": "技能卷轴"}
STORIES = {
    "forest": "晨光穿过叶片，森林把第一段勇气留在这里。",
    "island": "听见贝壳里的浪声，就想起那次跨海的旅程。",
    "snow": "雪山的晶光，记得你认真攻克过的每一道题。",
    "ruins": "古老的猫爪符石，珍藏遗迹中找回的知识。",
    "sky": "一枚轻盈云羽，记录向更高处出发的自己。",
    "stars": "在银河深处，努力的人会拾到属于自己的星光。",
}


def preview(g, item_id):
    """预览不调用装备/购买函数，金币、背包与当前外观均不变。"""
    out = copy.deepcopy(g)
    item = game.CATALOG[item_id]
    if item.get("character"):
        out["skin"] = item_id
    elif item.get("outfit"):
        if item.get("fit_character"):
            out["skin"] = item["fit_character"]
        out["outfit"] = item_id
    elif item.get("story_only"):
        finance.state(out)["companion"] = item_id
    elif item.get("slot"):
        out["equipment"][item["slot"]] = item_id
    elif item.get("title"):
        out["title"] = item_id
    return out


def view_item(g, item):
    owned = item["id"] in g["inventory"]
    equipped = item["id"] in [g["skin"], g["outfit"], g["title"], *g["equipment"].values(), finance.state(g)["companion"]]
    milestone = next((m for m in game.growth_status(g) if m["item"] == item["id"]), None)
    companion = next((c for c in finance.view(g)["companions"] if c["id"] == item["id"]), None)
    unlocked = owned or ((not milestone or milestone["unlocked"]) and (not companion or companion["unlocked"]))
    if item.get("slot") == "wonder":
        effect = " · ".join(f"{label} +{item[slot + '_percent']}%" for slot, label in (("xp", "经验"), ("coins", "金币")) if item[slot + "_percent"])
    elif item.get("slot"):
        effect = ("经验" if item["slot"] == "xp" else "金币") + f" +{item['bonus_percent']}%"
    else:
        effect = "切换冒险伙伴，所有姿态同步" if item.get("character") else "地图、战斗、头像同步换装" if item.get("outfit") else "把新称号挂在冒险名片上" if item.get("title") else "珍藏你的六地图冒险记忆"
    return {**item, "owned": owned, "equipped": equipped,
            "group": "characters" if item.get("character") else "outfits" if item.get("outfit") else item["category"],
            "rarity_name": game.RARITY_NAMES[item["rarity"]], "effect": effect,
            "story": item.get("story") or STORIES.get(item.get("biome") or item.get("outfit")) or "每一次认真学习，都让你的冒险收藏多一份光彩。",
            "wearable": bool(item.get("character") or item.get("outfit") or item.get("slot") or item.get("title") or companion),
            "unlocked": unlocked,
            "unlock_text": f"完成财管第{companion['unlock_chapter']}章可招募" if companion and not unlocked else f"通关 {milestone['clears']} 关上架" if milestone and not milestone["unlocked"] else "",
            "remaining": max(0, item["price"] - g["coins"]),
            "can_buy": not owned and unlocked and not item.get("earned_only") and g["coins"] >= item["price"]}


def view(g, category="all", owned_only=False):
    items = [view_item(g, item) for item in game.CATALOG.values()]
    if owned_only:
        return [i for i in items if i["owned"] and (category == "all" or i["group"] == category)]
    out = sorted([i for i in items if not i.get("starter")], key=lambda i: i.get("slot") != "wonder")
    for s in skills.view(g):
        out.append({**s, "id": "skill:" + s["id"], "skill_id": s["id"], "name": s["name"] + "卷轴",
                    "group": "skills", "rarity": "rare", "rarity_name": "技能", "effect": s["description"],
                    "story": "等级达到后自动学会。每次补充获得一次使用机会，也可用魔法墨水补充。",
                    "owned": False, "equipped": False, "wearable": False,
                    "unlock_text": "" if s["unlocked"] else f"Lv.{s['level']} 解锁",
                    "can_buy": s["unlocked"] and g["coins"] >= s["price"],
                    "remaining": max(0, s["price"] - g["coins"])})
    return [i for i in out if category == "all" or i["group"] == category]


def goal(g):
    item = game.CATALOG.get(g.get("wishlist"))
    return view_item(g, item) if item else None


def set_wishlist(progress, item_id):
    if item_id not in game.CATALOG or game.CATALOG[item_id].get("starter"):
        raise ValueError("请选择可兑换的冒险物品。")
    progress["game"]["wishlist"] = item_id
    return {"wishlist": item_id}
