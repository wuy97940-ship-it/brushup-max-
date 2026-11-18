"""圆宝团大商店与背包：统一目录、分页、预览和原子保存后的结果。"""
from __future__ import annotations

import copy
import math
import time
import tkinter as tk
import uuid

import customtkinter as ctk
import desktop_product as product
import desktop_suits as suits
import desktop_hunting as hunting
import desktop_growth as growth
import finance
import game
from desktop_effects import ConsumptionEffect
from desktop_window_resources import ManagedWindow
from app import C, _f, btn_ghost, btn_primary, btn_soft


SLOT_NAMES = {"outfit": "服装", "headwear": "头饰", "xp": "经验装备", "coins": "金币装备", "wonder": "奇物", "footwear": "鞋子", "pawgear": "爪套/翅套"}
RARITY_COLORS = {"普通": "#68778C", "稀有": "#2478C5", "传说": "#AE7B16"}
SUBCATEGORIES = {
    "角色": ["全部"], "消耗品": ["全部", "食物补给", "情绪恢复", "复苏用品", "魔法补给"],
    "装备": ["全部", "服装", "头饰", "经验装备", "金币装备", "奇物", "鞋子", "爪套/翅套"],
    "家装": ["全部", "家具", "家电", "装修", "装饰"], "藏品": ["全部"],
    "精灵": ["全部", *[rule["name"] for rule in hunting.CONFIG["rarities"].values()]],
}


class MarketCategoryButtons(ctk.CTkFrame):
    """分层目录的入口卡片，窗口变窄时改为单列。"""
    def __init__(self, master, values, command, descriptions=None, images=None):
        super().__init__(master, fg_color="transparent")
        self.values = list(values)
        self._selected = None
        self.buttons = {}
        self._columns = None
        for value in self.values:
            detail = (descriptions or {}).get(value, "点击进入")
            image = (images or {}).get(value)
            self.buttons[value] = btn_soft(self, text=value+"\n"+detail, image=image, compound="top", height=154,
                font=_f(14, "bold"), command=lambda key=value: command(key))
            self.buttons[value]._directory_image = image
        self.bind("<Configure>", self._arrange)
        self._arrange()

    def _arrange(self, event=None):
        columns = 2 if self.winfo_width()/self._get_widget_scaling() >= 530 else 1
        if columns == self._columns:
            return
        self._columns = columns
        for column in range(2):
            self.grid_columnconfigure(column, weight=1 if column < columns else 0, uniform="directory")
        for index, button in enumerate(self.buttons.values()):
            button.grid(row=index//columns, column=index%columns, sticky="ew", padx=5, pady=6)

    def cget(self, name):
        return self.values if name == "values" else super().cget(name)

    def get(self):
        return self._selected

    def set(self, value):
        self._selected = value


class MarketUIMixin:
    PAGE_SIZE = 12

    @staticmethod
    def _market_configure(widget, **values):
        # 卡片池复用时，相同文字/图片不再触发CTk重复绘制和尺寸回调。
        changed = {key: value for key, value in values.items() if widget.cget(key) != value}
        if changed:
            widget.configure(**changed)

    def _build_bag(self):
        self._build_market(shop=False)

    def _build_store(self, category=None, subcategory=None):
        self._build_market(shop=True)
        if category:
            self._set_market_category({"家具家电": "家装", "房间装修": "家装", "装饰": "家装"}.get(category, category))
            selected = subcategory or {"房间装修": "装修", "装饰": "装饰"}.get(category)
            if selected:
                self._set_market_subcategory(selected)

    def _build_market(self, *, shop):
        self._market_shop = shop
        self._market_level = "categories"
        self._market_category = None
        self._market_subcategory = "全部"
        self._market_page_index = 0
        self.market_cards = []
        self._market_card_pool = []
        self.market_visible_ids = []
        # 分类首页在全店翻页后仍可立即复用；最多四类各12张，离开再建货架时释放。
        self._market_first_page_images = {}
        self.market_result = getattr(self, "market_result", None)
        self._market_filter_cache = getattr(self, "_market_filter_cache", {})
        frame = self._scroll()
        self._heading(frame, "圆宝团大商店" if shop else "我的背包", "先选大分类，再选细分类，找到想要的物品。" if shop else "按分类查看已拥有的物品和精灵，选择伙伴一起同行。")
        self._market_wallet = self._text(frame, self._market_wallet_text(), bold=True, color=C["brand"])
        navigation = ctk.CTkFrame(frame, fg_color="transparent")
        navigation.pack(fill="x", pady=(8, 4))
        self._market_back = btn_ghost(navigation, text="← 返回上一级", width=130, command=self._market_go_up)
        self._market_back.pack(side="left")
        self._market_path = ctk.CTkLabel(navigation, text="", font=_f(12), anchor="w")
        self._market_path.pack(side="left", fill="x", expand=True, padx=10)
        categories = ["消耗品", "装备", "家装"] if shop else ["消耗品", "装备", "家装", "精灵", "藏品"]
        descriptions = {"消耗品": "食物、情绪、复苏与魔法补给", "装备": "服装、头饰、护符与鞋爪", "家装": "家具、家电、装修与装饰", "精灵": "按稀有度查看，设置同行", "藏品": "以前旅程获得的收藏"}
        self._market_category_control = MarketCategoryButtons(frame, categories, self._set_market_category, descriptions,
            self._market_directory_images(None,categories))
        self._market_category_control.pack(fill="x", pady=(10, 5))
        self._market_sub_host = ctk.CTkFrame(frame, fg_color="transparent")
        self._market_sub_host.pack(fill="x", pady=(0, 8))
        self._market_sub_controls = {}
        self._market_sub_control = None
        self._market_equipment_host = ctk.CTkFrame(frame, fg_color="transparent")
        self.market_slots = {}
        self._market_note = self._text(frame, "", size=11)
        self.market_grid = ctk.CTkFrame(frame, fg_color="transparent")
        self.market_grid.pack(fill="x", pady=5)
        for column in range(3):
            self.market_grid.grid_columnconfigure(column, weight=1, uniform="market")
        self._market_spirit_host = ctk.CTkFrame(frame, fg_color="transparent")
        pager = self._market_pager = ctk.CTkFrame(frame, fg_color="transparent")
        pager.pack(fill="x", pady=10)
        self.market_previous = btn_soft(pager, text="← 上一页", width=100, command=lambda: self._market_turn_page(-1))
        self.market_previous.pack(side="left")
        self.market_page_label = ctk.CTkLabel(pager, text="", font=_f(12))
        self.market_page_label.pack(side="left", expand=True)
        self.market_next = btn_soft(pager, text="下一页 →", width=100, command=lambda: self._market_turn_page(1))
        self.market_next.pack(side="right")
        btn_ghost(frame, text="去我的背包 →" if shop else "去圆宝团大商店 →",
                  command=lambda: self._show_page("bag" if shop else "shop")).pack(anchor="w", pady=8)
        if shop:
            btn_ghost(frame, text="金币不够 · 去基础学习", command=self._open_basic).pack(anchor="w", pady=4)
        else:
            btn_ghost(frame, text="布置我的家", command=self._open_room_editor).pack(anchor="w", pady=4)
        self._market_show_directory()

    def _market_wallet_text(self):
        return f"金币 {product.coin_text(self.g)}    建材 {product.materials(self.g)}"

    def _market_directory_images(self, category, values):
        roots={"消耗品":"food_cookie","装备":"outfit_finance_xiaoyuan_ledger","家装":"home_bed",
               "精灵":"spirit_puni","藏品":"equipment_xp_common"}
        images={}
        for value in values:
            key=roots[value] if category is None else roots[category]
            if category=="精灵" and value!="全部":
                key=next(item['id'] for item in hunting.SPIRITS.values() if hunting.CONFIG['rarities'][item['rarity']]['name']==value)
            elif category=="装备" and value=="套装":key=next(iter(suits.SUITS))
            elif category and value!="全部":
                key=next((item['id'] for item in product.SHOP_CATALOG.values() if item['category']==category and item['subcategory']==value),key)
            images[value]=self.sprites.item_icon(key,76) if key in hunting.SPIRITS else self.sprites.market_icon(key,76)
        return images

    def _market_go_up(self):
        if self._market_level == "items":
            self._market_level = "subcategories"
        else:
            self._market_level = "categories"
            self._market_category = None
        self._market_show_directory()

    def _market_show_directory(self):
        # 退出叶子页时取消旧图片请求；目录页不创建或解码商品图片。
        self._market_art_request = uuid.uuid4().hex
        self._market_images_ready = True
        self.market_cards = []
        self.market_visible_ids = []
        for card in self._market_card_pool:
            card["frame"].grid_remove()
        for host in (self._market_category_control, self._market_sub_host, self._market_equipment_host,
                     self.market_grid, self._market_spirit_host, self._market_pager):
            host.pack_forget()
        self._market_note.pack_forget()
        base = "大商店" if self._market_shop else "背包"
        self._market_back.configure(state="disabled" if self._market_level == "categories" else "normal")
        self._market_path.configure(text=base if self._market_level == "categories" else base+"  ›  "+self._market_category)
        if self._market_level == "categories":
            self._market_category_control.pack(fill="x", pady=8, after=self._market_path.master)
        else:
            self._market_update_subcategories()
            self._market_sub_host.pack(fill="x", pady=8, after=self._market_path.master)
        self._market_wallet.configure(text=self._market_wallet_text())

    def _market_show_items(self):
        self._market_level = "items"
        self._market_art_request = uuid.uuid4().hex
        self._market_images_ready = True
        self._market_category_control.pack_forget()
        self._market_sub_host.pack_forget()
        self._market_equipment_host.pack_forget()
        self._market_spirit_host.pack_forget()
        self._market_path.configure(text=("大商店" if self._market_shop else "背包")+"  ›  "+self._market_category+"  ›  "+self._market_subcategory)
        self._market_back.configure(state="normal")
        if not self._market_shop and self._market_category == "装备":
            if not self._market_equipment_host.winfo_children():
                self._build_equipment_slots(self._market_equipment_host)
            self._market_equipment_host.pack(fill="x", pady=5, after=self._market_path.master)
        self._market_note.pack(fill="x", pady=4, after=self._market_equipment_host if self._market_equipment_host.winfo_manager() else self._market_path.master)
        if self._market_category == "精灵":
            for card in self._market_card_pool:
                card["frame"].grid_remove()
            self.market_cards = []
            self.market_visible_ids = []
            self.market_grid.pack_forget()
            self._market_pager.pack_forget()
            self._market_spirit_host.pack(fill="x", pady=5, after=self._market_note)
            self._market_refresh_spirits()
        else:
            self.market_grid.pack(fill="x", pady=5, after=self._market_note)
            self._market_pager.pack(fill="x", pady=10, after=self.market_grid)
            self._refresh_market_display()

    def _market_refresh_spirits(self):
        host = self._market_spirit_host
        for child in host.winfo_children():
            child.destroy()
        team = [key for key in finance.companion_ids(self.g) if key in hunting.SPIRITS]
        limit = growth.companion_limit(self.g)
        owned = [item for item in hunting.SPIRITS.values() if item["id"] in self.g["inventory"]
                 and (self._market_subcategory == "全部" or hunting.CONFIG["rarities"][item["rarity"]]["name"] == self._market_subcategory)]
        names = "、".join(hunting.SPIRITS[key]["name"] for key in team) or "尚未选择"
        self._market_note.configure(text=f"已收服 {len(owned)} 只 · 同行 {len(team)}/{limit} · 当前同行：{names}")
        self._market_wallet.configure(text=self._market_wallet_text())
        self.bag_spirit_cards = {}
        self.bag_spirit_buttons = {}
        if not owned:
            self._text(host, "还没有收服这一类精灵，去猎场寻找新的伙伴吧。", size=13)
            btn_soft(host, text="前往精灵狩猎 →", command=lambda: self._show_page("hunting")).pack(anchor="w", pady=10)
            return
        if limit == 1:
            self._text(host, "精灵羁绊Ⅳ阶开放第二个同行名额；当前可以随时替换一只。", size=11)
        if hunting.active(self.g):
            self._text(host, "收服挑战进行中，结束挑战后可以调整同行。", size=11, color=C["red"])
        for item in owned:
            key = item["id"]
            card = self._card_frame(host)
            card.pack(fill="x", pady=7)
            image = self.sprites.item_icon(key, 110)
            label = ctk.CTkLabel(card, text="", image=image, width=125, height=125)
            label._market_image = image
            label.pack(side="left", padx=12, pady=10)
            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True, padx=8, pady=10)
            rarity = hunting.CONFIG["rarities"][item["rarity"]]["name"]
            self._text(content, item["name"]+" · "+rarity, size=16, bold=True, color=C["brand"])
            description = self._text(content, item["role"]+"\n"+item["story"], size=11)
            description.configure(wraplength=360)
            self._text(content, "正在跟随" if key in team else "已收服 · 可以跟随", size=12, color=C["brand"])
            self.bag_spirit_cards[key] = card
            self.bag_spirit_buttons[key] = {}
            disabled = hunting.active(self.g) or self._pending_transaction
            replacements = team if key not in team and limit > 1 and len(team) >= limit else [None]
            for previous in replacements:
                text = "替换"+hunting.SPIRITS[previous]["name"] if previous else "取消跟随" if key in team else "替换当前跟随" if team and limit == 1 else "让它跟随"
                button = btn_soft(content, text=text, command=lambda target=key, old=previous: self._market_follow_spirit(target, replace=old),
                                  state="disabled" if disabled else "normal", height=31)
                button.pack(anchor="w", pady=(4, 0))
                self.bag_spirit_buttons[key][previous] = button

    def _market_follow_spirit(self, identifier, *, replace=None):
        def follow(progress):
            result = hunting.equip_spirit(progress, identifier, replace=replace)
            result["flow"] = "market"
            return result
        result = self._market_commit(follow, {"action": "companion", "id": identifier})
        if result is None and self._pending_transaction:
            self._market_refresh_spirits()
        return result

    def _market_update_subcategories(self):
        options = SUBCATEGORIES.get(self._market_category, ["全部"])
        if self._market_shop and self._market_category == "装备":
            options = ["全部", "套装", *options[1:]]
        current = getattr(self, "_market_subcategory", "全部")
        self._market_subcategory = current if current in options else "全部"
        key = tuple(options)
        control = self._market_sub_controls.get(key)
        if control is None:
            descriptions = {key: "查看这一类物品" for key in options}
            if self._market_category == "精灵":
                for key in options:
                    count = sum(s["id"] in self.g["inventory"] and (key == "全部" or hunting.CONFIG["rarities"][s["rarity"]]["name"] == key) for s in hunting.SPIRITS.values())
                    descriptions[key] = f"已收服 {count} 只"
            control = MarketCategoryButtons(self._market_sub_host, options, self._set_market_subcategory, descriptions,
                self._market_directory_images(self._market_category,options))
            self._market_sub_controls[key] = control
        if control is not self._market_sub_control:
            if self._market_sub_control is not None:
                self._market_sub_control.pack_forget()
            control.pack(fill="x")
            self._market_sub_control = control
        self._market_sub_control.set(self._market_subcategory)

    def _set_market_category(self, value):
        if value not in self._market_category_control.cget("values"):
            raise ValueError("请选择可用的大分类")
        self._market_category, self._market_subcategory, self._market_page_index = value, "全部", 0
        self._market_category_control.set(value)
        if self._market_shop:
            self._product_filter = value
        else:
            self._bag_filter = value
        self._market_level = "subcategories"
        self._market_show_directory()

    def _set_store_filter(self, value):
        self._set_market_category(value)
        self._set_market_subcategory("全部")

    def _set_bag_filter(self, value):
        self._set_market_category(value)
        self._set_market_subcategory("全部")

    def _set_market_subcategory(self, value):
        if self._market_category is None or value not in self._market_sub_control.cget("values"):
            raise ValueError("请选择当前大分类的细分类")
        self._market_subcategory, self._market_page_index = value, 0
        self._market_sub_control.set(value)
        self._market_show_items()

    def _market_items(self):
        category, subcategory = self._market_category, self._market_subcategory
        key = (category, subcategory)
        if key not in self._market_filter_cache:
            self._market_filter_cache[key] = [] if category == "藏品" else product.shop_items(category, subcategory)
        items = list(self._market_filter_cache[key])
        items = [item for item in items if item.get('kind')!='hero']
        if self._market_shop and category in ("全店", "全部", "装备") and subcategory in ("全部", "套装"):
            items = suits.shop_entries() + items
        if not self._market_shop:
            items = [item for item in items if product.owned_count(self.g, item["id"]) > 0]
            if category in ("全部", "藏品"):
                for identifier in self.g.get("inventory", []):
                    if identifier in product.SHOP_CATALOG or identifier in hunting.SPIRITS:
                        continue
                    original = game.CATALOG.get(identifier, {})
                    items.append({**original, "id": identifier, "name": original.get("name", identifier),
                                  "category": "藏品", "subcategory": "旧版藏品", "kind": original.get("kind", "collection"),
                                  "description": original.get("description", original.get("story", "已拥有的旧版藏品，继续保留在背包。")),
                                  "display_rarity": original.get("rarity", "藏品"), "legacy": True})
        return items

    def _market_turn_page(self, delta):
        self._market_page_index = max(0, min(self._market_total_pages-1, self._market_page_index+delta))
        self._refresh_market_display()

    def _refresh_market_display(self):
        if not getattr(self, "market_grid", None) or not self.market_grid.winfo_exists():
            return
        if self._product_page not in ("shop", "bag"):
            return
        if self._market_level != "items":
            self._market_show_directory()
            return
        if self._market_category == "精灵":
            self._market_refresh_spirits()
            return
        items = self._market_items()
        self._market_total_pages = max(1, math.ceil(len(items)/self.PAGE_SIZE))
        self._market_page_index = min(self._market_page_index, self._market_total_pages-1)
        page = items[self._market_page_index*self.PAGE_SIZE:(self._market_page_index+1)*self.PAGE_SIZE]
        ids = [item["id"] for item in page]
        self._market_images_ready = False
        self._market_art_request = uuid.uuid4().hex
        request = self._market_art_request
        first_page = self._market_shop and self._market_page_index == 0 and self._market_subcategory == "全部"
        retained = self._market_first_page_images.get(self._market_category, {}) if first_page else {}
        cached_art = {identifier: retained.get(identifier) or self.sprites.cached_item_icon(identifier, 118) for identifier in ids}
        missing = [identifier for identifier, art in cached_art.items() if art is None]
        future = self.sprites.warm_items_async(missing) if missing else None
        if ids != self.market_visible_ids:
            while len(self._market_card_pool) < len(page):
                index = len(self._market_card_pool)
                self._market_card_pool.append(self._market_item_card(page[index], index))
            self.market_cards = self._market_card_pool[:len(page)]
            for index, card in enumerate(self._market_card_pool):
                if index >= len(page):
                    card["frame"].grid_remove()
                    continue
                item = page[index]
                different_item = card["id"] != item["id"]
                card.update(id=item["id"], item=item)
                card["frame"].grid()
                art = cached_art[item["id"]]
                self._market_configure(card["image"], image=art, text="" if art else "载入图片…")
                card["image"]._market_image = art
                self._market_configure(card["name_label"], text=item["name"])
                self._market_configure(card["grade_label"], text=item.get("subcategory", item["category"]) + " · " + item.get("display_rarity", "普通"),
                                               text_color=RARITY_COLORS.get(item.get("display_rarity"), C["text_sub"]))
                self._market_configure(card["description_label"], text=item.get("description", ""))
                if different_item:
                    card["image"].bind("<Button-1>", lambda event, i=item: self._open_market_detail(i))
                    card["detail_button"].configure(command=lambda i=item: self._open_market_detail(i))
                self._update_market_card(card)
            self.market_visible_ids = ids
        else:
            for card in self.market_cards:
                self._update_market_card(card)
        self._market_configure(self._market_wallet, text=self._market_wallet_text())
        suit_count = sum(item.get('kind') == 'suit' for item in items)
        count_note = f"{suit_count} 套完整套装 · {len(items)-suit_count} 件单品" if suit_count else f"共 {len(items)} 件"
        self._market_note.configure(text=count_note+" · 每页最多12项 · 点击看大图、效果和试穿" if items else "这一类暂时是空的，去大商店挑选喜欢的物品吧。")
        self.market_page_label.configure(text=f"第 {self._market_page_index+1} / {self._market_total_pages} 页")
        self.market_previous.configure(state="normal" if self._market_page_index else "disabled")
        self.market_next.configure(state="normal" if self._market_page_index+1 < self._market_total_pages else "disabled")
        if future is None:
            self._market_images_ready = True
            self._remember_market_first_page()
        else:
            self.after(10, lambda: self._market_load_images(future, request))

    def _remember_market_first_page(self):
        if (self._market_shop and self._market_page_index == 0 and self._market_subcategory == "全部"
                and self._market_category in ("全店", "消耗品", "装备", "家装")):
            self._market_first_page_images[self._market_category] = {
                card["id"]: card["image"]._market_image for card in self.market_cards
                if card["image"]._market_image is not None
            }

    def _market_load_images(self, future, request):
        if request != getattr(self, "_market_art_request", None) or not self.market_grid.winfo_exists():
            return
        if not future.done():
            self.after(10, lambda: self._market_load_images(future, request))
            return
        try:
            future.result()
            for card in self.market_cards:
                art = self.sprites.market_icon(card["id"], 118)
                if card["image"]._market_image is not art:
                    card["image"].configure(image=art, text="" if art else "图片未找到")
                    card["image"]._market_image = art
            self._market_images_ready = True
            self._remember_market_first_page()
        except (OSError, ValueError) as error:
            self._market_note.configure(text="商品图片载入失败，请重新打开分类。" + str(error))

    def _market_item_card(self, item, index):
        card = self._card_frame(self.market_grid)
        card.grid(row=index//3, column=index%3, sticky="nsew", padx=5, pady=6)
        art = ctk.CTkLabel(card, text="载入图片…", width=130, height=124)
        art._market_image = None
        art.pack(pady=(10, 3))
        art.bind("<Button-1>", lambda event, i=item: self._open_market_detail(i))
        name = self._text(card, item["name"], size=14, bold=True, color=C["text"])
        name.configure(wraplength=215)
        grade = self._text(card, item.get("subcategory", item["category"]) + " · " + item.get("display_rarity", "普通"), size=10,
                           color=RARITY_COLORS.get(item.get("display_rarity"), C["text_sub"]))
        description = self._text(card, item.get("description", ""), size=10)
        description.configure(wraplength=215, height=48)
        status = self._text(card, "", size=11, color=C["brand"])
        status.configure(wraplength=215)
        button = btn_soft(card, text="查看详情", height=31, command=lambda i=item: self._open_market_detail(i))
        button.pack(fill="x", padx=12, pady=(4, 11))
        data = {"id": item["id"], "item": item, "frame": card, "image": art,
                "name_label": name, "grade_label": grade, "description_label": description,
                "status_label": status, "detail_button": button, "buy_button": button}
        return data

    def _update_market_card(self, data):
        item = data["item"]
        if item.get('kind') == 'suit':
            status = suits.shop_status(self.g, item['id'])
            text = f"四件已齐 · 已拥有 4/4" if not status['missing_items'] else f"已拥有 {status['owned_parts']}/4 · 补齐需 {status['missing_coins']} 金币"
            if status['equipped']:
                text += ' · 已穿戴'
            self._market_configure(data['status_label'], text=text)
            self._market_configure(data['detail_button'], text='整套试穿 / 查看配套')
            return
        owned = 1 if item.get("legacy") else product.owned_count(self.g, item["id"])
        equipped = False if item.get("legacy") else product.is_equipped(self.g, item["id"])
        text = f"已拥有 {owned}" + (" · 已穿戴" if equipped else "")
        if item["category"] == "家装":
            placed = product.placed_count(self.g, item["id"])
            if item.get("kind") in ("wallpaper", "floor"):
                placed = int(product.state(self.g)["room"].get(item["kind"]) == item["id"])
            text += f" · 已布置 {placed} · 可用 {max(0, owned-placed)}"
            if item.get("kind") in ("wallpaper", "floor"):
                used = sum(room.get(item["kind"]) == item["id"] for room in product.house_state(self.g)["floors"].values())
                text = f"已拥有样式 {owned} · 已应用 {used}层 · 可反复使用"
            elif item.get("kind") == "floor_upgrade":
                text = f"已扩建" if owned else "待扩建 · " + item["description"]
        if self._market_shop:
            status = product.purchase_status(self.g, item["id"])
            currency = "金币" if item.get("currency") == "coins" else "建材"
            text = f"{item['price']} {currency} · " + text
            self._market_configure(data["detail_button"], text="查看 / 购买" if status["allowed"] else "查看 · 已拥有" if status["owned"] and item.get("max_quantity") == 1 else "查看购买条件")
        else:
            self._market_configure(data["detail_button"], text={"角色": "查看 / 切换", "消耗品": "选择伙伴并使用", "装备": "查看 / 试穿", "家装": "查看 / 布置"}.get(item["category"], "查看藏品"))
        self._market_configure(data["status_label"], text=text)

    def _build_equipment_slots(self, parent):
        panel = self._card_frame(parent)
        panel.pack(fill="x", pady=(5, 9))
        self._market_slots_title = self._text(panel, "当前穿戴 · " + product.HEROES[product.hero_id(self.g)]["name"], bold=True, color=C["brand"])
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(4, 12))
        self.market_slots = {}
        for index, (slot, title) in enumerate(SLOT_NAMES.items()):
            row.grid_columnconfigure(index % 4, weight=1, uniform="slots")
            cell = ctk.CTkFrame(row, fg_color="transparent")
            cell.grid(row=index // 4, column=index % 4, sticky="nsew", padx=3)
            identifier = self.g.get(slot) if slot in product.PERSONAL_SLOTS else self.g.get("equipment", {}).get(slot)
            item = product.SHOP_CATALOG.get(identifier)
            art = self.sprites.market_icon(identifier, 46) if identifier else None
            label = ctk.CTkLabel(cell, text="" if art else "—", image=art, height=48)
            label._market_image = art
            label.pack()
            ctk.CTkLabel(cell, text=title, font=_f(11, "bold")).pack()
            name_label = ctk.CTkLabel(cell, text=item["name"] if item else "未穿戴", font=_f(10), wraplength=122, height=32)
            name_label.pack()
            button = btn_ghost(cell, text="卸下", height=25, width=65, state="normal" if identifier else "disabled",
                               command=lambda s=slot: self._market_unequip(s))
            button.pack(pady=2)
            self.market_slots[slot] = {"id": identifier, "button": button, "frame": cell, "image": label, "name_label": name_label}

    def _update_equipment_slots(self):
        if self._product_page != "bag" or not getattr(self, "market_slots", None):
            return
        self._market_slots_title.configure(text="当前穿戴 · " + product.HEROES[product.hero_id(self.g)]["name"])
        for slot, cell in self.market_slots.items():
            identifier = self.g.get(slot) if slot in product.PERSONAL_SLOTS else self.g.get("equipment", {}).get(slot)
            item = product.SHOP_CATALOG.get(identifier)
            art = self.sprites.market_icon(identifier, 46) if identifier else None
            cell["id"] = identifier
            cell["image"].configure(image=art, text="" if art else "—")
            cell["image"]._market_image = art
            cell["name_label"].configure(text=item["name"] if item else "未穿戴")
            cell["button"].configure(state="normal" if identifier else "disabled")

    def _market_item(self, item_or_id):
        if isinstance(item_or_id, dict):
            return item_or_id
        if item_or_id in suits.SUITS:
            return next(item for item in suits.shop_entries() if item['id'] == item_or_id)
        return product.SHOP_CATALOG[item_or_id]

    def _open_market_detail(self, item_or_id, *, target=None):
        item = self._market_item(item_or_id)
        existing = getattr(self, "market_window", None)
        if existing and existing.winfo_exists():
            existing.destroy()
        if item.get('kind') == 'suit':
            self.market_window = self._open_suit_preview(item['id'], from_shop=True)
            return self.market_window
        win = ManagedWindow(self)
        self.market_window = win
        win.title(item["name"] + " · 商品详情")
        win.geometry("780x780")
        win.minsize(680, 630)
        win.transient(self)
        win.item_id, win.nonce, win.action_result = item["id"], uuid.uuid4().hex, None
        win.item = item
        content = ctk.CTkScrollableFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=13, pady=10)
        self._text(content, item["name"], size=23, bold=True, color=C["brand"])
        self._text(content, item.get("subcategory", item["category"]) + " · " + item.get("display_rarity", "普通"), size=11,
                   color=RARITY_COLORS.get(item.get("display_rarity"), C["text_sub"]))
        art_row = ctk.CTkFrame(content, fg_color="transparent")
        art_row.pack(fill="x", pady=3)
        image = self.sprites.market_icon(item["id"], 245)
        win.art = ctk.CTkLabel(art_row, image=image, text="" if image else "商品图片准备中", width=265, height=260)
        win.art._market_image = image
        win.art.pack(side="left", padx=8)
        win.preview = ctk.CTkLabel(art_row, text="", width=265, height=260)
        win.preview.pack(side="left", padx=6)
        if item["category"] == "家装":
            from desktop_home_art import HomeScene
            self._text(content, "房间效果预览 · 不改变当前布置", size=11, bold=True)
            win.home_scene = HomeScene(content, self.sprites, self._home_product_preview(item), height=220, compact=True)
            win.home_scene.pack(fill="x", padx=12, pady=7)
        self._text(content, item.get("description", ""), size=12).configure(wraplength=650)
        if item.get("slot"):
            fit = product.HEROES.get(item.get("fit_character"), {}).get("name", "三位伙伴")
            self._text(content, f"穿戴位置：{SLOT_NAMES.get(item['slot'], item['slot'])} · 适用：{fit}。试穿只改变预览。\n独立头饰会替换服装套装自带帽子，保留衣身。", size=11)
        win.target_ids = list(product.state(self.g)["heroes"]) if item["category"] == "消耗品" else list(product.HEROES)
        default = target or (item.get("fit_character") if item.get("fit_character") else product.hero_id(self.g))
        if item["category"] == "角色":
            default = item["id"]
        if default not in win.target_ids:
            default = win.target_ids[0] if win.target_ids else product.hero_id(self.g)
        win.target_id = default
        labels = [product.HEROES[key]["name"] + (" · 未解锁" if key not in product.state(self.g)["heroes"] else "") for key in win.target_ids]
        win.target_map = dict(zip(labels, win.target_ids))
        if item["category"] in ("消耗品", "装备"):
            self._text(content, "使用对象" if item["category"] == "消耗品" else "试穿伙伴", size=11, bold=True)
            # 无可选用对象（如新档未领主角）时禁用下拉，避免点击占位项触发 KeyError。
            win.target_control = ctk.CTkOptionMenu(content, values=labels or ["尚无伙伴"],
                command=(lambda value: self._market_target_changed(win, win.target_map[value])) if labels else None,
                state="normal" if labels else "disabled")
            win.target_control.pack(fill="x", padx=14, pady=5)
            if default in win.target_ids:
                win.target_control.set(labels[win.target_ids.index(default)])
        win.preview_note = self._text(content, "", size=12, color=C["brand"])
        win.operation_area = ctk.CTkFrame(content, fg_color="transparent")
        win.operation_area.pack(fill="x", padx=14, pady=9)
        win.feedback = self._text(content, "", size=12, color=C["brand"])
        btn_ghost(content, text="关闭详情", command=win.destroy).pack(pady=8)
        self._market_detail_refresh(win)
        win.after(20, win.lift)
        return win

    def _market_target_changed(self, win, hero_id):
        win.target_id = hero_id
        self._market_detail_refresh(win)

    def _market_detail_refresh(self, win):
        item, target = win.item, win.target_id
        preview = product.hero_preview(self.g, target)
        slot = item.get("slot")
        fit = item.get("fit_character")
        compatible = not fit or fit == target
        if slot and compatible:
            if slot in product.PERSONAL_SLOTS:
                preview[slot] = item["id"]
            else:
                preview.setdefault("equipment", {})[slot] = item["id"]
        pose = "sleep" if product.state(self.g)["heroes"].get(target, {}).get("energy", 1) <= 0 else "idle"
        # 家装在下方使用房间预览；不先给说明栏挂上角色图片。
        picture = None if item["category"] == "家装" else self.sprites.portrait(preview, 245, pose)
        win.preview.configure(image=picture)
        win.preview._market_image = picture
        for child in win.operation_area.winfo_children():
            child.destroy()
        win.action_button, win.buy_button, win.use_button, win.equip_button = None, None, None, None
        owned = 1 if item.get("legacy") else product.owned_count(self.g, item["id"])
        win.preview_note.configure(text=f"已拥有 {owned}" + (" · 当前试穿" if slot and compatible else " · 该服装不适用这位伙伴" if slot else ""))
        if item["category"] == "家装":
            placed = product.placed_count(self.g, item["id"])
            if item.get("kind") in ("wallpaper", "floor"):
                placed = int(product.state(self.g)["room"].get(item["kind"]) == item["id"])
            win.preview_note.configure(text=f"共拥有 {owned} · 已布置 {placed} · 可用 {max(0, owned-placed)}")
            if item.get("kind") in ("wallpaper", "floor"):
                win.preview_note.configure(text="购买后解锁装修样式，可在各楼层反复使用，切回原样不消耗样式。")
            elif item.get("kind") == "floor_upgrade":
                win.preview_note.configure(text=f"目前{product.house_state(self.g)['unlocked_floors']}层 · 扩建后{item['target_floor']*32}格总空间。已有房间与家具保留。")
            win.preview.configure(image=None, text="下方为房间效果预览\n购买后可在背包布置\n各楼层独立保存")
        if item.get("legacy"):
            win.feedback.configure(text="这件旧版藏品已保留。可从学习工具进入原有经营建筑与剧情。")
            return
        status = product.purchase_status(self.g, item["id"])
        currency = "金币" if item["currency"] == "coins" else "建材"
        balance = self.g["coins"] if item["currency"] == "coins" else product.materials(self.g)
        purchase_line = f"价格 {item['price']} {currency} · 当前余额 {balance}"
        if status["allowed"]:
            purchase_line += f" · 购买后 {balance-item['price']}"
        else:
            purchase_line += " · " + status["reason"]
        self._text(win.operation_area, purchase_line, size=11).configure(wraplength=610)
        buy = btn_primary(win.operation_area, text=f"确认购买 · {item['price']}{currency}" if status["allowed"] else "已拥有" if status["owned"] and item.get("max_quantity") == 1 else "暂不可购买，请查看上方条件",
                          state="normal" if status["allowed"] and not self._pending_transaction else "disabled",
                          command=lambda: self._market_buy(item["id"], win.nonce, win))
        buy.pack(fill="x", pady=5)
        win.buy_button = buy
        if item["category"] == "消耗品":
            try:
                effect = product.consumption_preview(self.g, item["id"], hero_id=target)
                resource = {'mana': '魔法', 'mood': '情绪'}.get(effect.get('resource'), '体力')
                line = f"{resource} {effect['before']:g} → {effect['after']:g} · 实际恢复 {effect['gain']:g}点"
                if effect.get("overflow"):
                    line += f" · 超出上限 {effect['overflow']:g}点"
                win.preview_note.configure(text=product.HEROES[target]["name"] + "：" + line)
                use_allowed = owned > 0
            except ValueError as error:
                win.preview_note.configure(text=str(error))
                use_allowed = False
            # 演出资源在确认使用之前准备，保存成功后只创建画布并启动时钟。
            for pose_name in ("sleep", "sad", "idle", "happy", "celebrate"):
                self.sprites.actor_photo(product.hero_preview(self.g, target), pose_name, 245)
            self.sprites.market_photo(item["id"], 95)
            self.sprites.market_photo(item["id"], 48)
            self.sprites.effect_photo("revival_pill", 48)
            self.sprites.market_photo("food_cookie", 48)
            win.use_button = btn_soft(win.operation_area, text="确认给" + product.HEROES[target]["name"] + "使用",
                                       state="normal" if use_allowed and not self._pending_transaction else "disabled",
                                       command=lambda: self._market_consume(item["id"], win.nonce, target, win))
            win.use_button.pack(fill="x", pady=5)
            win.action_button = win.use_button
        elif item["category"] == "角色" and owned:
            current = product.hero_id(self.g) == item["id"]
            win.equip_button = btn_soft(win.operation_area, text="正在同行" if current else "设为同行伙伴", state="disabled" if current else "normal",
                                         command=lambda: self._market_equip(item["id"], item["id"], win))
            win.equip_button.pack(fill="x", pady=5)
            win.action_button = win.equip_button
        elif slot and owned:
            allowed = compatible and target in product.state(self.g)["heroes"]
            win.equip_button = btn_soft(win.operation_area, text="确认穿戴" if allowed else "请先解锁适用伙伴",
                                         state="normal" if allowed else "disabled", command=lambda: self._market_equip(item["id"], target, win))
            win.equip_button.pack(fill="x", pady=5)
            win.action_button = win.equip_button
        elif item["category"] == "家装" and owned:
            win.action_button = btn_soft(win.operation_area, text="去布置 / 移动", command=lambda: self._market_go_room(win, item["id"]))
            win.action_button.pack(fill="x", pady=5)

    def _home_product_preview(self, item):
        import copy
        candidate = {"game": copy.deepcopy(self.g)}
        g = candidate["game"]
        room = product.state(g)["room"]
        if item["kind"] == "floor_upgrade":
            room.clear()
            room.update(placements={}, wall={}, wallpaper=None, floor=None)
        elif item["kind"] in ("wallpaper", "floor"):
            room[item["kind"]] = item["id"]
        else:
            product.state(g)["stock"][item["id"]] = product.placed_count(g, item["id"]) + 1
            if item["kind"] == "wall":
                product.place(candidate, item["id"], slot="center")
            else:
                for y in range(product.CONFIG["room"]["rows"]):
                    for x in range(product.CONFIG["room"]["columns"]):
                        try:
                            product.place(candidate, item["id"], x=x, y=y)
                            return g
                        except ValueError:
                            continue
        return g

    def _market_go_room(self, win, identifier):
        win.destroy()
        self._open_room_editor(identifier)

    def _market_commit(self, mutate, context):
        if self._pending_transaction:
            return None
        win = context.get("window")
        if win and win.winfo_exists():
            for button in (getattr(win, "buy_button", None), getattr(win, "action_button", None)):
                if button and button.winfo_exists():
                    button.configure(state="disabled")
        result = self._commit(mutate)
        if result is None:
            if self._pending_transaction:
                self._market_pending_action = context
                if win and win.winfo_exists():
                    win.feedback.configure(text="尚未保存，没有播放效果。请点击侧栏「重试保存」；同一笔操作会继续，不会再次扣费。")
            elif win and win.winfo_exists():
                self._market_detail_refresh(win)
            return None
        context["saved_at"] = time.perf_counter()
        self._market_after_saved(result, context)
        return result

    def _market_buy(self, identifier, token=None, window=None):
        context = {"action": "buy", "id": identifier, "window": window}
        return self._market_commit(lambda p: product.buy(p, identifier, token or uuid.uuid4().hex), context)

    def _buy_product(self, identifier, token=None):
        return self._market_buy(identifier, token)

    def _market_consume(self, identifier, token=None, hero_id=None, window=None):
        target = hero_id or product.hero_id(self.g)
        context = {"action": "consume", "id": identifier, "hero": target, "window": window}
        return self._market_commit(lambda p: product.consume(p, identifier, token or uuid.uuid4().hex, hero_id=target), context)

    def _consume_product(self, identifier, token=None):
        return self._open_market_detail(identifier)

    def _market_equip(self, identifier, target=None, window=None):
        context = {"action": "equip", "id": identifier, "hero": target, "window": window}
        return self._market_commit(lambda p: product.equip(p, identifier, uuid.uuid4().hex, hero_id=target), context)

    def _market_unequip(self, slot):
        context = {"action": "unequip", "slot": slot}
        return self._market_commit(lambda p: product.unequip(p, slot, uuid.uuid4().hex), context)

    def _market_after_saved(self, result, context):
        self.market_result = {"action": context["action"], "item": context.get("id"), "hero": context.get("hero"), "result": copy.deepcopy(result), "saved": True}
        win = context.get("window")
        if context["action"] == "companion":
            if self._product_page == "bag":
                self._refresh_market_display()
            return
        if context["action"] == "consume":
            if win and win.winfo_exists():
                win.destroy()
            self.market_effect = ConsumptionEffect(self, product.SHOP_CATALOG[context["id"]], context["hero"], result,
                reduced_motion=product.state(self.g)["settings"].get("reduced_motion", False))
            self.market_result["effect_latency"] = self.market_effect._started_at - context.get("saved_at", self.market_effect._started_at)
            self._refresh_market_display()
            return
        if context["action"] in ("equip", "unequip"):
            if win and win.winfo_exists():
                win.destroy()
            if self._product_page in ("bag", "shop"):
                self._refresh_market_display()
                self._update_equipment_slots()
            self._show_market_result(context, result)
            return
        self._refresh_market_display()
        if win and win.winfo_exists():
            win.nonce = uuid.uuid4().hex
            win.action_result = result
            self._market_detail_refresh(win)
            win.feedback.configure(text="购买成功，已保存到背包。" + ("可直接选择伙伴使用。" if win.item["category"] == "消耗品" else ""))
        self._show_market_result(context, result)

    def _show_market_result(self, context, result):
        previous = getattr(self, "market_result_window", None)
        if previous and previous.winfo_exists():
            previous.destroy()
        win = ManagedWindow(self)
        self.market_result_window = win
        win.title("操作成功 · 已保存")
        win.geometry("470x530")
        win.transient(self)
        identifier = context.get("id")
        item = product.SHOP_CATALOG.get(identifier)
        target = context.get("hero") or (identifier if item and item["category"] == "角色" else product.hero_id(self.g))
        show_actor = context["action"] in ("equip", "unequip") or item and item["category"] == "角色"
        if item or show_actor:
            image = self.sprites.portrait(product.hero_preview(self.g, target), 245, "idle") if show_actor else self.sprites.market_icon(identifier, 180)
            label = ctk.CTkLabel(win, text="", image=image)
            label._market_image = image
            label.pack(pady=(17, 4))
            win.result_art = label
        text = {"buy": "购买成功，已放入背包", "equip": "穿戴 / 同行设置已保存", "unequip": "已卸下，物品仍在背包"}[context["action"]]
        ctk.CTkLabel(win, text=text, font=_f(18, "bold"), text_color=C["brand"]).pack(pady=8)
        if item:
            ctk.CTkLabel(win, text=item["name"] + f" · 已拥有 {product.owned_count(self.g, identifier)}", font=_f(13)).pack(pady=4)
        if context["action"] in ("equip", "unequip"):
            bonuses = product.bonuses(self.g)
            ctk.CTkLabel(win, text=f"经验 +{bonuses['xp']:g}% · 金币 +{bonuses['coins']:g}%", font=_f(12)).pack(pady=3)
        ctk.CTkLabel(win, text=self._market_wallet_text(), font=_f(12)).pack(pady=6)
        if context["action"] == "buy" and item:
            btn_soft(win, text="查看 / 使用这件物品", command=lambda: (win.destroy(), self._open_market_detail(identifier))).pack(pady=5)
            btn_ghost(win, text="去我的背包", command=lambda: (win.destroy(), self._show_page("bag"))).pack(pady=3)
        btn_primary(win, text="继续逛逛", command=win.destroy).pack(pady=9)
