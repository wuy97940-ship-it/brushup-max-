"""电脑版统一商品目录；旧商品编号与价格沿用原始配置。"""
from __future__ import annotations

import json

import store


def _config(name: str) -> dict:
    return json.loads(store.resource_path("assets/" + name).read_text(encoding="utf-8"))


PRODUCT = _config("product_config.json")
GAME = _config("game_config.json")
FINANCE = _config("finance_config.json")
WONDERS = _config("wonder_config.json")
RARITIES = {**GAME["rarities"], **_config("shop_config.json")["rarities"]}
SLOTS = ("outfit", "headwear", "xp", "coins", "wonder", "footwear", "pawgear")
PERSONAL_SLOTS = ("outfit", "headwear", "footwear", "pawgear")
CATEGORIES = ("角色", "消耗品", "装备", "家装")
SUBCATEGORIES = {
    "角色": ("角色",), "消耗品": ("食物补给", "情绪恢复", "复苏用品", "魔法补给"),
    "装备": ("服装", "头饰", "经验装备", "金币装备", "奇物", "鞋子", "爪套/翅套"),
    "家装": ("家具", "家电", "装修", "装饰"),
}


def make_catalog() -> dict[str, dict]:
    result = {}

    def add(raw: dict, category: str, subcategory: str, kind: str, slot=None) -> None:
        rarity = raw.get("rarity", "common")
        item = {**raw, "category": category, "subcategory": subcategory, "kind": kind,
                "currency": raw.get("currency", "coins"), "rarity": rarity,
                "display_rarity": "传说" if rarity in ('epic', 'legendary') else RARITIES[rarity]["name"], "fit_character": raw.get("fit_character"),
                "slot": slot, "description": raw.get("description") or raw.get("story", ""),
                "image": "assets/market/items/" + raw["id"] + ".png",
                "thumbnail": "assets/market/thumbs/" + raw["id"] + ".png"}
        if category in ("角色", "装备"):
            item["max_quantity"] = 1
        if category == '装备':
            rarity = 'legendary' if rarity == 'epic' else rarity
            tier = PRODUCT['equipment_tiers'][rarity]
            item.update(rarity=rarity, display_rarity=tier['name'], price=tier['price'],
                        xp_percent=tier['xp_percent'], coins_percent=tier['coins_percent'], mana_percent=tier['mana_percent'])
            item['description'] = f"经验+{tier['xp_percent']}% · 金币+{tier['coins_percent']}% · 魔法上限+{tier['mana_percent']}%；同槽一件，各槽相加，奖励加成开场冻结。"
            # 旧字段仅供兼容展示，真实奖励统一读取三项属性。
            item['bonus_percent'] = tier['xp_percent'] if slot == 'xp' else tier['coins_percent'] if slot == 'coins' else 0
        result[item["id"]] = item

    for raw in PRODUCT["heroes"]:
        add(raw, "角色", "角色", "hero")
    for raw in PRODUCT["items"]:
        if raw["category"] == "消耗品":
            add(raw, "消耗品", {"food": "食物补给", "calm": "情绪恢复", "revive": "复苏用品", "mana": "魔法补给"}[raw["kind"]], raw["kind"])
        else:
            sub = "家电" if raw["id"] == "home_washer" else {"家具家电": "家具", "房间装修": "装修", "装饰": "装饰"}[raw["category"]]
            add(raw, "家装", sub, raw["kind"])
    for raw in FINANCE["outfits"]:
        add(raw, "装备", "服装", "outfit", "outfit")
    for biome in GAME["biomes"]:
        rarity = biome["rarity"]
        add({"id": "outfit_" + biome["id"], "name": biome["outfit"], "rarity": rarity,
             "price": RARITIES[rarity]["price"], "outfit": biome["id"],
             "description": "三位伙伴都能佩戴的" + biome["outfit"] + "，可与服装同时穿戴。"}, "装备", "头饰", "headwear", "headwear")
    for slot, label, sub in (("xp", "经验护符", "经验装备"), ("coins", "金币铃铛", "金币装备")):
        for rarity, definition in GAME["rarities"].items():
            add({"id": "equipment_" + slot + "_" + rarity, "name": definition["name"] + label,
                 "price": definition["price"], "rarity": rarity, "bonus_percent": definition["bonus_percent"],
                 "description": "合资格奖励的" + ("经验" if slot == "xp" else "金币") + "+" + str(definition["bonus_percent"]) + "%；开场锁定加成。"},
                "装备", sub, "equipment", slot)
    for raw in WONDERS["items"]:
        add(raw, "装备", "奇物", "wonder", "wonder")
        result[raw["id"]]["required_clears"] = next(m["clears"] for m in WONDERS["milestones"] if m["item"] == raw["id"])
    for raw in PRODUCT['new_equipment']:
        sub={'outfit':'服装','headwear':'头饰','footwear':'鞋子','pawgear':'爪套/翅套'}[raw['slot']]
        add(raw, '装备', sub, raw['slot'] if raw['slot'] in ('outfit','headwear') else 'equipment', raw['slot'])
    return result


SHOP_CATALOG = make_catalog()


def shop_items(category: str = "全店", subcategory: str = "全部") -> list[dict]:
    return [item for item in SHOP_CATALOG.values()
            if category in ("全店", "全部") or item["category"] == category
            if subcategory == "全部" or item["subcategory"] == subcategory]
