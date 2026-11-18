"""电脑版5.1界面，保留原题目渲染、结构化大题、收藏与原子保存机制。"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import random
import shutil
import time
import tkinter as tk
from tkinter import messagebox
import uuid

import customtkinter as ctk
import desktop_product as product
import desktop_mood as mood
from desktop_home_art import HomeScene
from desktop_market_ui import MarketUIMixin
from desktop_window_resources import GuiGarbageCollector, release_resources
import game
from game_art import AdventureScene
from game_ui import AdventureApp
import finance
import store
from desktop_persistence import save_with_events, waiting, defer_close
import world_scenes
from app import App, C, _f, btn_ghost, btn_primary, btn_soft, is_correct


class ProductApp(MarketUIMixin, AdventureApp):
    _pages = {**AdventureApp._pages, "shop": "_build_store", "heroes": "_build_heroes", "tools": "_build_tools"}

    def _windows_set_titlebar_color(self, color_mode):
        """仅设置本窗口的DWM颜色，避免工具包隐藏/重显并嵌套处理启动消息。"""
        import sys
        if sys.platform != 'win32' or self._deactivate_windows_window_header_manipulation:
            return
        import ctypes
        from ctypes import wintypes as W
        try:
            user = ctypes.windll.user32
            dwm = ctypes.windll.dwmapi
            user.GetParent.argtypes = [W.HWND]
            user.GetParent.restype = W.HWND
            dwm.DwmSetWindowAttribute.argtypes = [W.HWND, W.DWORD, ctypes.c_void_p, W.DWORD]
            dwm.DwmSetWindowAttribute.restype = ctypes.c_long
            hwnd = user.GetParent(self.winfo_id())
            value = W.BOOL(color_mode.lower() == 'dark')
            result = dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
            if result:
                # 旧Windows保留同一窗口的兼容属性；不隐藏窗口或启动嵌套消息循环。
                dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        except (OSError, tk.TclError):
            # 不支持窗口颜色时沿用系统标题栏，不影响学习、保存和正常关窗。
            pass

    def __init__(self):
        self._gui_gc = GuiGarbageCollector()
        self._product_booting = True
        self._product_ready = False
        self._product_page = "home"
        self._product_filter = "全店"
        self._bag_filter = "全部"
        self._starter_selected = None
        self._market_pending_action = None
        self._migration_backup = None
        self._room_selected = None
        self._room_location = None
        self._room_instance = None
        self._last_feedback_pose = None
        self._boot_started = time.perf_counter()
        try:
            super().__init__()
        except Exception:
            self._gui_gc.close()
            raise
        self._product_booting = False
        if self.winfo_exists():
            self.title("小圆冒险世界 · 原创公开版 6.1.0-public.1")
            self._commit(lambda p: product.login(p))
            closing = getattr(self, '_close_after_initialization', False)
            if not closing:
                self._show_page("home")
                # 正常进入主消息循环后按最终几何绘制，不提前显示或重建窗口外框。
            self.startup_seconds = time.perf_counter() - self._boot_started
            if not closing:
                self._gui_gc.start(self)
            migration = product.state(self.g).get("migration", {})
            if not closing and migration.get("from_version") is not None and not migration.get("acknowledged"):
                self.after(100, self._show_migration_notice)

    @property
    def g(self):
        existing = self.progress.get("game")
        if self._product_ready and isinstance(existing, dict) and existing.get("product", {}).get("version") == 3:
            return existing
        legacy = isinstance(existing, dict)
        from desktop_challenge import install_question_map
        install_question_map(self.questions)
        if legacy and existing.get("product", {}).get("version", 0) < 3:
            source = store.app_data_dir() / store.PROGRESS_FILE
            if source.exists():
                backup = source.with_name("progress-before-v520-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json")
                try:
                    shutil.copy2(source, backup)
                except OSError as error:
                    messagebox.showerror("升级前备份失败", "旧存档尚未迁移。请检查存档目录权限和磁盘空间后重新打开。\n" + str(error))
                    raise
                self._migration_backup = str(backup)
        g = game.ensure_game(self.progress, self.questions)
        product.initialize(self.progress, self.questions, legacy=legacy)
        from static_campaigns import seal
        seal(self.progress)
        if self._migration_backup:
            product.state(g).setdefault("migration", {})["backup_path"] = self._migration_backup
        self._product_ready = True
        # 产品初始化已完成旧版规范化，随后login一次原子保存即可，避免继承层重复写档。
        self._growth_migration_pending = False
        return g

    def _show_migration_notice(self):
        if not self.winfo_exists():
            return
        migration = product.state(self.g).get("migration", {})
        if migration.get("acknowledged"):
            return
        locked = [product.HEROES[key]["name"] for key in migration.get("locked_heroes", []) if key in product.HEROES]
        text = "已升级为圆宝团大商店 5.1.0。\n学习记录、成绩、金币、经验、建材和已购物品继续保留。"
        if migration.get("backup_path"):
            text += "\n迁移前的旧存档已完整备份：\n" + migration["backup_path"]
        if locked:
            text += "\n旧版自动赠送、未购买的伙伴已恢复待解锁：" + "、".join(locked) + "。归档体力和外观保留，解锁后恢复。"
        if migration.get("preserved_purchased_heroes"):
            text += "\n有购买记录的伙伴继续保留。"
        text += "\n服装与头饰分为两个槽位，可分别穿戴。"
        messagebox.showinfo("本次存档迁移说明", text)
        self._commit(lambda p: product.state(p["game"])["migration"].update(acknowledged=True))

    def _build_sidebar(self):
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=15, pady=(10, 6))
        self.avatar_label = ctk.CTkLabel(brand, text="", image=self.sprites.portrait(self.g, 54))
        self.avatar_label.pack(anchor="w")
        self.avatar_label.bind("<Button-1>", lambda event: self._navigate("heroes", self._build_heroes))
        ctk.CTkLabel(brand, text="小圆冒险世界", font=_f(17, "bold"), text_color=C["brand"]).pack(anchor="w", pady=(3, 0))
        self._hero_status = ctk.CTkLabel(brand, text="", font=_f(11), justify="left", anchor="w", text_color=C["text_sub"])
        self._hero_status.pack(fill="x", pady=(5, 3))
        self._energy_bar = ctk.CTkProgressBar(brand, height=6, progress_color=C['primary'])
        self._energy_bar.pack(fill="x", pady=4)
        self._mana_status = ctk.CTkLabel(brand, text='', font=_f(11), anchor='w', text_color='#348AD4')
        self._mana_status.pack(fill='x', pady=(3, 0))
        self._mana_bar = ctk.CTkProgressBar(brand, height=6, progress_color='#348AD4')
        self._mana_bar.pack(fill='x', pady=4)
        self._mood_status = ctk.CTkLabel(brand, text='', font=_f(11), anchor='w', text_color='#D55691')
        self._mood_status.pack(fill='x', pady=(3, 0))
        self._mood_status.bind('<Button-1>', lambda event: self._open_mood_shop())
        self._mood_bar = ctk.CTkProgressBar(brand, height=7, progress_color='#EC6FA9', fg_color='#F4DAE7')
        self._mood_bar.pack(fill='x', pady=4)
        self._wallet_label = ctk.CTkLabel(brand, text="", font=_f(11), text_color=C["brand"], anchor="w")
        self._wallet_label.pack(fill="x", pady=(3, 4))
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=15, pady=13)
        self.retry_save_btn = btn_primary(footer, text="重试保存", height=30, command=self._retry_pending)
        self.theme_control = ctk.CTkSegmentedButton(footer, values=["浅色", "深色", "系统"], command=self._on_theme_change, font=_f(10))
        self.theme_control.pack(fill="x", pady=5)
        self.theme_control.set({"light": "浅色", "dark": "深色", "system": "系统"}.get(self.progress.get("theme"), "系统"))
        self.version_label=ctk.CTkLabel(footer, text="v6.1.0-public.1 · 原创公开版", font=_f(10), text_color=C["text_sub"])
        self.version_label.pack(anchor="w", pady=4)
        # 固定头像和保存入口，导航在小窗口及放大字体时滚动。
        self._navigation_frame = ctk.CTkScrollableFrame(self.sidebar, height=1,
            corner_radius=0, fg_color="transparent", border_width=0)
        self._navigation_frame.pack(fill="both", expand=True, pady=(0, 4))
        entries = [("home", "◇  冒险地图", self._build_home), ("practice", "⚑  比武场", self._build_practice),
                   ("roles", "♧  角色馆", self._build_roles), ("hunting", "✧  精灵狩猎", self._build_hunting),
                   ("town", "⌂  经营小镇", self._build_finance_town), ("bag", "▣  我的背包", self._build_bag),
                   ("shop", "✦  圆宝团大商店", self._build_store),
                   ("growth", "☆  成长与技能", self._build_growth),
                   ("workshop", "⚒  技能工坊", self._build_workshop)]
        self.nav_btns = {}
        for key, title, builder in entries:
            button = ctk.CTkButton(self._navigation_frame, text=title, anchor="w", height=39, corner_radius=11,
                font=_f(13), fg_color="transparent", hover_color=C["side_hover"], text_color=C["text"],
                command=lambda k=key, b=builder: self._navigate(k, b))
            button.pack(fill="x", padx=13, pady=3)
            self.nav_btns[key] = button
        for key, title, builder in (("tools", "学习工具与设置", self._build_tools),
                                    ("saves", "存档记录", self._build_save_records),
                                    ("restart", "重新开始游戏", self._build_restart_game)):
            button = btn_ghost(self._navigation_frame, text=title, height=30, font=_f(11), command=lambda k=key, b=builder: self._navigate(k, b))
            button.pack(fill="x", padx=15, pady=3)
            self.nav_btns[key] = button
        self._sync_avatar()

    def _hero_status_text(self, text, g):
        return text

    def _sync_after_commit(self):
        if not hasattr(self, "avatar_label") or not self.avatar_label.winfo_exists():
            return
        g, s = self.g, product.state(self.g)
        if not self._sidebar_visible():
            # 答题时只更新可见心情和场景数据，返回侧栏时一次刷新完整资源。
            if s['starter_claimed']:
                self._sync_quiz_mood(product.active_hero(g))
            if self._game_scene:
                self._game_scene.g = g
            self._sidebar_dirty = True
            return
        self._sync_avatar()

    def _sync_avatar(self):
        if not hasattr(self, "avatar_label") or not self.avatar_label.winfo_exists():
            return
        g, s = self.g, product.state(self.g)
        self._sidebar_dirty = False
        import desktop_growth as growth
        mana_visible = s['starter_claimed'] and growth.level(g) >= growth.CONFIG['mana'].get('unlock_level', 10)
        if mana_visible:
            if not self._mana_status.winfo_manager():
                self._mana_status.pack(fill='x', pady=(3, 0), before=self._wallet_label)
                self._mana_bar.pack(fill='x', pady=4, before=self._wallet_label)
        else:
            self._mana_status.pack_forget()
            self._mana_bar.pack_forget()
        if not s["starter_claimed"]:
            self._hero_status.configure(text=self._hero_status_text("选择一位免费同行伙伴", g))
            self._energy_bar.set(0)
            self._mana_bar.set(0)
            self._mana_status.configure(text='魔法 · 等待伙伴同行')
            self._mood_status.configure(text='情绪 · 等待伙伴同行')
            self._mood_bar.set(0)
            self._wallet_label.configure(text="先领取主角，再开始冒险")
            return
        hero = product.active_hero(g)
        self._sync_quiz_mood(hero)
        mood_text = f"情绪 {mood.value(hero)}/100 · {mood.label(hero)}"
        if self._mood_status.cget('text') != mood_text:
            self._mood_status.configure(text=mood_text, text_color=mood.color(hero))
            self._mood_bar.configure(progress_color=mood.color(hero))
            self._mood_bar.set(mood.value(hero) / 100)
        pose = "sleep" if hero["energy"] <= 0 else "tired" if hero["energy"] / hero["maximum"] <= .3 else "idle"
        portrait = self.sprites.portrait(g, 54, pose)
        if self.avatar_label.cget('image') is not portrait:
            self.avatar_label.configure(image=portrait)
        name = product.HEROES[product.hero_id(g)]["name"]
        status = "休眠 · 需要还魂丹" if hero["energy"] <= 0 else "低落 · 可以休息或鼓励" if hero["low_mood"] else "疲惫 · 记得补给" if pose == "tired" else "准备好一起出发"
        text = f"{name}  Lv.{product.level(g)}\n体力 {hero['energy']/100:g}/{hero['maximum']/100:g} · {hero['energy']/hero['maximum']:.0%}"
        self._hero_status.configure(text=self._hero_status_text(text, g))
        energy_fraction = hero['energy'] / hero['maximum']
        self._energy_bar.set(energy_fraction)
        self._energy_bar.configure(progress_color=C['red'] if energy_fraction <= .2 else '#F49A38' if energy_fraction < .5 else C['primary'])
        mana_text = f"魔法 {hero['mana']}/{hero['mana_maximum']}"
        if self._mana_status.cget('text') != mana_text:
            self._mana_status.configure(text=mana_text)
        mana_fraction = hero['mana'] / hero['mana_maximum'] if hero['mana_maximum'] else 0
        self._mana_bar.configure(progress_color='#8ACDF5' if mana_fraction < .2 else '#348AD4')
        if self._mana_bar.get() != mana_fraction:
            self._mana_bar.set(mana_fraction)
        self._wallet_label.configure(text=f"金币 {product.coin_text(g)}   建材 {product.materials(g)}")
        if self._game_scene:
            self._game_scene.g = g

    def _show_sidebar(self):
        super()._show_sidebar()
        if getattr(self, '_sidebar_dirty', False):
            self._sync_avatar()

    def _build_quiz_mood(self, parent):
        panel = ctk.CTkFrame(parent, fg_color='transparent', width=170)
        panel.pack(side='right', padx=(10, 8))
        self._quiz_mood_status = ctk.CTkLabel(panel, text='', font=_f(11), anchor='e')
        self._quiz_mood_status.pack(fill='x')
        self._quiz_mood_bar = ctk.CTkProgressBar(panel, width=165, height=5, fg_color='#F4DAE7')
        self._quiz_mood_bar.pack(fill='x', pady=(1, 2))
        self._sync_quiz_mood(product.active_hero(self.g))

    def _open_mood_shop(self):
        self._show_page('shop')
        self._set_market_category('消耗品')
        self._set_market_subcategory('情绪恢复')

    def _sync_quiz_mood(self, hero):
        label = getattr(self, '_quiz_mood_status', None)
        if label is None or not label.winfo_exists():
            return
        text = f"情绪 {mood.value(hero)}/100 · {mood.label(hero)}"
        if label.cget('text') != text:
            label.configure(text=text, text_color=mood.color(hero))
            self._quiz_mood_bar.configure(progress_color=mood.color(hero))
            self._quiz_mood_bar.set(mood.value(hero) / 100)

    def _show_page(self, name, builder=None):
        self._last_interaction_at=time.monotonic()
        if self._product_booting:
            return
        if not self._flush_scratch():
            return
        if not product.state(self.g)["starter_claimed"] and name not in ("saves", "restart"):
            stage = product.state(self.g)['onboarding']['stage']
            name, builder = ('welcome', self._build_welcome) if stage == 'welcome' else ('heroes', self._build_heroes)
        self._product_page = name
        super()._show_page(name, builder)

    def _navigate(self, key, builder):
        self._flush_draft()
        if self._pending_transaction:
            return
        self.current_qids = []
        self._game_mode = False
        self._show_page(key, builder)

    def _text(self, parent, text, *, size=12, bold=False, color=None, pady=4):
        label = ctk.CTkLabel(parent, text=text, font=_f(size, "bold" if bold else "normal"),
                             text_color=color or C["text_sub"], wraplength=780, justify="left", anchor="w")
        label.pack(fill="x", padx=14, pady=pady)
        return label

    def _build_welcome(self):
        frame = self._scroll()
        self._heading(frame, '欢迎来到小圆冒险世界！', '知识是你的力量，伙伴会陪你一起成长。选一位主角，开启新的冒险吧。')
        card = self._card_frame(frame)
        card.pack(fill='x', pady=18)
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=15, pady=18)
        for identifier in product.HEROES:
            ctk.CTkLabel(row, text=product.HEROES[identifier]['name'], compound='top',
                         image=self.sprites.portrait(product.hero_preview(self.g, identifier), 135), font=_f(15, 'bold')).pack(side='left', expand=True)
        self._text(card, '从零出发 · 首次任选一位免费伙伴 · 绿色体力，蓝色魔法', size=15, bold=True, color=C['brand'])
        self.welcome_start_button = btn_primary(frame, text='开始冒险 →', height=46, command=self._begin_adventure)
        self.welcome_start_button.pack(fill='x', padx=8, pady=12)

    def _begin_adventure(self):
        if self._commit(product.begin_onboarding):
            self._show_page('heroes')

    def _build_heroes(self):
        frame, g = self._scroll(), self.g
        first = not product.state(g)["starter_claimed"]
        if first:
            self._starter_selected = product.state(g)['onboarding'].get('selected')
        self._heading(frame, "选一位伙伴，一起爱上刷题" if first else "我的同行伙伴",
                      "首次任选一位免费主角；点击卡片预选，再确认领取。其余主角在猎场通过考试获得。" if first else "等级与学习进度共用，体力、魔法和外观分别保存。其余主角在猎场通过考试获得。")
        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", pady=12)
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1, uniform="heroes")
        for col, (identifier, definition) in enumerate(product.HEROES.items()):
            card = self._card_frame(grid)
            card.grid(row=0, column=col, sticky="nsew", padx=5, pady=6)
            preview = product.hero_preview(g, identifier)
            ctk.CTkLabel(card, text="", image=self.sprites.portrait(preview, 155)).pack(pady=(18, 4))
            self._text(card, definition["name"], size=19, bold=True, color=C["brand"])
            label = self._text(card, definition["description"], size=11)
            label.configure(wraplength=235)
            if first:
                selected = self._starter_selected == identifier
                card.configure(border_width=2 if selected else 1, border_color=C["brand"] if selected else C["border"])
                button = btn_soft(card, text="已预选 ✓" if selected else "预选" + definition["name"], command=lambda key=identifier: self._preselect_hero(key))
            elif identifier in product.state(g)["heroes"]:
                hero = product.state(g)["heroes"][identifier]
                self._text(card, f"体力 {hero['energy']/100:g}/{hero['maximum']/100:g}" + (" · 休眠" if not hero["energy"] else ""), size=11)
                button = btn_soft(card, text="正在同行" if product.hero_id(g) == identifier else "切换伙伴", command=lambda key=identifier: self._switch_hero(key))
                if product.hero_id(g) == identifier:
                    button.configure(state="disabled")
            else:
                button = btn_soft(card, text="前往角色馆挑战", command=lambda: self._show_page("roles"))
            button.pack(fill="x", padx=14, pady=(12, 18))
        if first:
            btn_ghost(frame, text="帮我随机推荐一位", command=self._random_hero).pack(pady=12)
            selected_name = product.HEROES.get(self._starter_selected, {}).get("name", "一位伙伴")
            self.starter_confirm_button = btn_primary(frame, text="确认免费领取" + selected_name, height=42,
                state="normal" if self._starter_selected else "disabled", command=lambda: self._claim_hero(self._starter_selected))
            self.starter_confirm_button.pack(fill="x", padx=8, pady=6)
        else:
            btn_ghost(frame, text="返回冒险地图", command=lambda: self._show_page("home")).pack(pady=12)

    def _random_hero(self):
        identifier = random.SystemRandom().choice(list(product.HEROES))
        self._preselect_hero(identifier)

    def _preselect_hero(self, identifier):
        if self._commit(lambda p: product.preselect_starter(p, identifier)):
            self._starter_selected = identifier
            self._show_page("heroes")

    def _claim_hero(self, identifier):
        if identifier not in product.HEROES:
            return
        if self._commit(lambda p: product.claim_starter(p, identifier)):
            self._show_page("home")

    def _switch_hero(self, identifier):
        if self._commit(lambda p: product.switch_hero(p, identifier)):
            self._show_page("heroes")

    def _build_home(self):
        self._game_mode = False
        frame, g = self._scroll(), self.g
        self._heading(frame, "四大知识世界，等你点亮", "十题一小关：普通首通3金币、Boss首通5金币，章通关另奖10金币。")
        summary = product.state(g).get("offline_summary")
        if summary and summary["days"]:
            if product.state(g).get('version') == 3:
                losses='、'.join(f"{product.HEROES[key]['name']} {points:g}点" for key,points in summary.get('heroes',{}).items())
                self._text(frame, f"已结算{summary['days']}个未完成10题的自然日：{losses or '各伙伴体力已为0'}。每日达标，所有伙伴免扣。")
            else:
                self._text(frame, f"离开了{summary['days']}个完整日，{product.HEROES[summary['hero']]['name']}体力减少{summary['points']:g}点。每天固定扣10点，升级只增加上限。")
        hero = product.active_hero(g)
        mood_card = self._card_frame(frame)
        mood_card.pack(fill='x', pady=8)
        self._text(mood_card, f"心情 {mood.value(hero)}/100 · {mood.label(hero)}", size=16, bold=True, color=mood.color(hero))
        mood_rules=product.CONFIG['mood']
        self._text(mood_card, f"通关 +{mood_rules['stage_clear_gain']} · 答错 −{mood_rules['wrong_loss']} · 闯关失败额外 −{mood_rules['stage_failure_loss']}。玩具与出游券每次消耗一个，按各自幅度恢复心情。", size=11)
        btn_soft(mood_card, text='玩具与出游券 →', command=self._open_mood_shop).pack(anchor='w', padx=16, pady=(0, 12))
        if hero["energy"] <= 0:
            card = self._card_frame(frame)
            card.pack(fill="x", pady=8)
            self._text(card, "体力为0，请选择还魂或重新开始。学习和施法暂停，商店、背包与历史仍可查看。", bold=True, color=C["brand"])
            btn_primary(card, text="还魂 · 600金币", command=lambda: self._show_page("shop")).pack(side="left", padx=14, pady=12)
            btn_soft(card, text="重新开始整个游戏", command=self._on_reset).pack(side="left", pady=12)
        current = g.get("active")
        if current and not current["settled"]:
            btn_primary(frame, text="继续上次冒险 →", height=38, command=lambda: self._start_stage(current["stage_id"])).pack(fill="x", pady=6)
        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", pady=8)
        self._home_world_cards = []
        self._home_world_grid = grid
        self._home_world_columns = None
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform="worlds")
        for col, world in enumerate(g["product_campaign"]["worlds"]):
            card = self._card_frame(grid)
            card.grid(row=col//2, column=col%2, sticky="nsew", padx=5, pady=6)
            self._home_world_cards.append(card)
            scene = AdventureScene(card, self.sprites, g, biome=world["biome"], height=145)
            scene.pack(fill="x", padx=8, pady=(8, 2))
            self._text(card, world["name"], size=18, bold=True, color=C["brand"])
            label = self._text(card, world["subtitle"], size=11)
            label.configure(wraplength=240)
            sequence = product.ordered_stages(g, world["id"])
            count = sum(bool(g["results"].get(identifier, {}).get("cleared")) for identifier in sequence)
            completed = sum(all(g["results"].get(identifier, {}).get("cleared") for identifier in chapter["stages"]) for chapter in world["chapters"])
            self._text(card, f"点亮 {count}/{len(sequence)} 关\n章节 {completed}/{len(world['chapters'])}", size=12)
            progress = ctk.CTkProgressBar(card, height=7)
            progress.pack(fill="x", padx=14, pady=10)
            progress.set(count / len(sequence) if sequence else 0)
            btn_primary(card, text="进入世界 →", command=lambda wid=world["id"]: self._open_world(wid)).pack(fill="x", padx=14, pady=(3, 15))
        def arrange_worlds(event):
            if event.width < 150:
                return
            columns = 2 if event.width >= grid._get_widget_scaling() * 540 else 1
            if columns == self._home_world_columns:
                return
            self._home_world_columns = columns
            for col in range(2):
                grid.grid_columnconfigure(col, weight=1 if col < columns else 0,
                    uniform="worlds" if col < columns else "", minsize=0)
            for index, card in enumerate(self._home_world_cards):
                card.grid_configure(row=index // columns, column=index % columns)
        grid.bind("<Configure>", arrange_worlds, add="+")
        self._text(frame, "地图点亮代表完成；错题经过间隔复习，才记录为掌握。", size=11)
        btn_ghost(frame, text="基础学习与完整题型筛选", command=self._open_basic).pack(anchor="w", padx=12, pady=12)

    def _open_world(self, world_id):
        self._commit(lambda p: p["game"].update(world=world_id))
        def build():
            frame, g = self._scroll(), self.g
            world = next(w for w in g["product_campaign"]["worlds"] if w["id"] == world_id)
            btn_ghost(frame, text="← 四个世界", command=lambda: self._show_page("home")).pack(anchor="w", pady=5)
            self._heading(frame, world["name"], world["subtitle"])
            for chapter in world["chapters"]:
                card = self._card_frame(frame)
                card.pack(fill="x", pady=5)
                count = sum(bool(g["results"].get(key, {}).get("cleared")) for key in chapter["stages"])
                self._text(card, chapter["title"], size=15, bold=True, color=C["text"])
                self._text(card, f"点亮 {count}/{len(chapter['stages'])} 关" + (" · 已完成" if count == len(chapter["stages"]) else ""))
                open_ = product.can_play(g, chapter["stages"][0])
                btn_soft(card, text="查看章节地图 →" if open_ else "查看前置条件", command=lambda cid=chapter["id"]: self._open_chapter(cid)).pack(anchor="e", padx=14, pady=(0, 10))
        self._show_page("home", build)

    def _open_chapter(self, chapter_id):
        if not chapter_id.startswith("v5:"):
            return super()._open_chapter(chapter_id)
        def build():
            frame, g = self._scroll(), self.g
            world = next(w for w in g["product_campaign"]["worlds"] if any(ch["id"] == chapter_id for ch in w["chapters"]))
            chapter = next(ch for ch in world["chapters"] if ch["id"] == chapter_id)
            btn_ghost(frame, text="← " + world["name"], command=lambda: self._open_world(world["id"])).pack(anchor="w", pady=5)
            self._heading(frame, chapter["title"], "普通关80%通关、首通3金币；Boss90%通关、首通5金币。独立全对三星，技能助力最高两星，案例自评一星。")
            for offset in range(0, len(chapter["stages"]), 10):
                keys = chapter["stages"][offset:offset+10]
                nodes = [{"id": key, "name": g["product_campaign"]["levels"][key]["name"],
                          "stars": g["results"].get(key, {}).get("best_stars", 0), "available": product.can_play(g,key),
                          "kind": g["product_campaign"]["levels"][key]["kind"],
                          "cleared": bool(g["results"].get(key, {}).get("cleared")),
                          "current": key == product.next_stage(g,world_id=world["id"])} for key in keys]
                scene = AdventureScene(frame,self.sprites,g,biome=world["biome"],scene_id=world_scenes.chapter_scene(g,world['id'],chapter_id),height=110*math.ceil(len(keys)/4)+45,nodes=nodes,on_node=self._select_stage)
                scene.pack(fill="x", pady=6)
            for key in chapter["stages"]:
                item, result = g["product_campaign"]["levels"][key], g["results"].get(key,{})
                row = self._card_frame(frame)
                row.pack(fill="x",pady=3)
                label = "承接旧版通关 · 星级待重打" if result.get("legacy_migrated") else "★"*result.get("best_stars",0)
                self._text(row,f"{item['name']} · {len(item['qids'])}题  {label}",size=12)
                btn_soft(row,text="重打" if result.get("cleared") else "开始" if product.can_play(g,key) else "前置条件",
                         height=29,command=lambda sid=key:self._select_stage(sid)).pack(anchor="e",padx=12,pady=(0,7))
        self._show_page("home", build)

    def _select_stage(self, identifier):
        if product.can_play(self.g,identifier):
            self._start_stage(identifier,restart=bool(self.g["results"].get(identifier,{}).get("cleared")))
        else:
            item=self.g["product_campaign"]["levels"][identifier]
            sequence=product.ordered_stages(self.g,item["world_id"])
            previous=sequence[sequence.index(identifier)-1]
            previous_item=self.g["product_campaign"]["levels"][previous]
            if messagebox.askyesno("前置关卡",f"需要先完成{previous_item['chapter_title']} · {previous_item['name']}。前往该章节吗？"):
                self._open_chapter(previous_item["chapter_id"])

    def _build_practice(self):
        frame=self._scroll()
        self._heading(frame,"重难点比武场","当前学科跨章节重难点切磋，优先有明确出处的真题；使用提示的题不计独立有效分。")
        card=self._card_frame(frame)
        card.pack(fill="x",pady=10)
        worlds=self.g["product_campaign"]["worlds"]
        names=[world["name"] for world in worlds]
        self._arena_world=ctk.CTkOptionMenu(card,values=names,command=lambda value:self._arena_update_chapters())
        self._arena_world.pack(fill="x",padx=20,pady=(18,8))
        self._arena_chapter=ctk.CTkOptionMenu(card,values=["请选择章节"])
        self._arena_chapter.pack(fill="x",padx=20,pady=8)
        self._arena_count=ctk.CTkOptionMenu(card,values=["5题","10题","20题"])
        self._arena_count.set("10题")
        self._arena_count.pack(fill="x",padx=20,pady=8)
        self._arena_difficulty=ctk.CTkOptionMenu(card,values=["入门 · 60%目标","标准 · 80%目标","进阶 · 90%目标"])
        self._arena_difficulty.set("标准 · 80%目标")
        self._arena_difficulty.pack(fill="x",padx=20,pady=8)
        self._arena_weak=ctk.CTkCheckBox(card,text="薄弱题优先",font=_f(12))
        self._arena_weak.pack(anchor="w",padx=20,pady=10)
        self._arena_update_chapters()
        btn_primary(card,text="准备切磋 →",height=42,command=self._start_arena).pack(fill="x",padx=20,pady=(10,18))
        a=self.progress.get("practice")
        if a and a.get("product_mode")=="arena" and not a["settled"]:
            btn_soft(frame,text="继续上次切磋",command=self._resume_practice).pack(fill="x",pady=8)
        btn_ghost(frame,text="基础学习 · 不参加对战也可以正常刷题",command=self._open_basic).pack(anchor="w",pady=12)

    def _arena_update_chapters(self):
        world=next(w for w in self.g["product_campaign"]["worlds"] if w["name"]==self._arena_world.get())
        names=[ch["title"] for ch in world["chapters"]]
        self._arena_chapter.configure(values=names or ["暂无章节"])
        self._arena_chapter.set(names[0] if names else "暂无章节")

    def _start_arena(self):
        world=next(w for w in self.g["product_campaign"]["worlds"] if w["name"]==self._arena_world.get())
        chapter=next(ch for ch in world["chapters"] if ch["title"]==self._arena_chapter.get())
        qids=list(dict.fromkeys(qid for key in chapter["stages"] for qid in self.g["product_campaign"]["levels"][key]["qids"] if not store.is_subjective(self.qmap[qid])))
        random.SystemRandom().shuffle(qids)
        if self._arena_weak.get():
            qids.sort(key=lambda qid:qid not in self.progress["wrong_book"])
        qids=qids[:int(self._arena_count.get().replace("题",""))]
        if not qids:
            messagebox.showinfo("没有客观题","该章节只有案例题，请通过基础学习或冒险案例关练习。")
            return
        rate=60 if self._arena_difficulty.get().startswith("入门") else 90 if self._arena_difficulty.get().startswith("进阶") else 80
        target=math.ceil(len(qids)*rate/100)
        if not messagebox.askyesno("NPC练习对手",f"本场{len(qids)}题，对手目标{target}题。\n高于目标为胜，相同为平；正式提交每题消耗0.2点体力。开始吗？"):
            return
        a=self._commit(lambda p:product.start_practice(p,qids,mode="arena",name=chapter["title"]+" · NPC切磋",target=target,chapter_key=chapter["id"]))
        if a:
            self._open_practice(a)

    def _open_basic(self):
        self._show_page("practice",lambda:App._build_home(self))

    def _build_finance_town(self):
        frame,g=self._scroll(),self.g
        due=product.review_queue(g,self.qmap)
        pending=product.review_queue(g,self.qmap,due_only=False)
        self._heading(frame,"经营小镇 · 我的家",f"建材 {product.materials(g)} · 到期错题 {len(due)} · 待巩固 {len(pending)}。复习让知识更牢，也让家更温暖。")
        row=ctk.CTkFrame(frame,fg_color="transparent")
        row.pack(fill="x",pady=8)
        for title,action in (("复习错题得建材",self._start_review),("购买家装",lambda:self._show_page("shop",lambda:self._build_store("家具家电"))),
                             ("布置我的家",self._open_room_editor)):
            btn_primary(row,text=title,command=action,height=35).pack(side="left",padx=(0,8))
        self._home_floor_navigation(frame)
        self._home_scene=HomeScene(frame,self.sprites,g)
        self._home_scene.pack(fill="x",pady=10)
        self._text(frame,"正式独立纠错得4建材；至少24小时后再次独立答对得6建材。刚看解析10分钟内重做不发纠错奖励。",size=11)
        if not pending:
            self._text(frame,"目前没有待复习错题。可以完成每日五题巩固或章节首次通关，获得少量建材。")
            btn_soft(frame,text="去巩固知识",command=self._open_basic).pack(anchor="w",pady=7)
        elif not due:
            self._text(frame,"错题正在等待间隔复习，可以先练习；未到期时不领取阶段建材。")
            btn_soft(frame,text="提前练习错题",command=lambda:self._start_review(due_only=False)).pack(anchor="w",pady=7)
        hero=product.active_hero(g)
        self._text(frame, f"情绪 {mood.value(hero)}/100 · {mood.label(hero)}", size=15, bold=True, color=mood.color(hero))
        self._text(frame, '独立答对恢复8情绪；连续不同题答错减少12。情绪≤20时额外消耗0.6体力/题（每天最多3）和2魔法/题（每天最多30；十级后生效）。', size=11)
        if mood.value(hero) < 100 and hero['energy'] > 0:
            btn_soft(frame,text="休息十分钟 · 恢复情绪（不补体力/魔法）",command=self._rest_hero).pack(anchor="w",pady=8)
            btn_ghost(frame,text='暖心饮 · 情绪恢复40 →',command=lambda:self._show_page('bag',lambda:self._build_bag('消耗品'))).pack(anchor='w',pady=4)
        for qid in pending[:12]:
            q,rec=self.qmap[qid],product.state(g)["reviews"][qid]
            label=("自评" if rec.get("self_assessed") else "")+rec["status"]
            remaining=max(0,math.ceil((rec["next_due"]-time.time())/60))
            number=q.get("source_ref",{}).get("original_question_number") or q.get("num") or q.get("no") or q.get("number")
            suffix=f" · 原题号{number}" if number else " · "+q.get("type","")
            self._text(frame,f"{q.get('chapter','')}{suffix}  {label}"+(f" · 约{remaining}分钟后到期" if remaining else " · 可复习"),size=11)

    def _start_review(self,due_only=True):
        qids=product.review_queue(self.g,self.qmap,due_only=due_only)[:10]
        if not qids:
            messagebox.showinfo("错题复习","暂时没有到期错题。可以去基础学习巩固，或稍后再来。")
            return
        a=self._commit(lambda p:product.start_practice(p,qids,mode="review",name="家园错题复习"))
        if a:
            self._open_practice(a)

    def _rest_hero(self):
        result=self._commit(lambda p:product.rest(p))
        if result:
            messagebox.showinfo("伙伴休息",f"情绪恢复到{result['mood']}/100。体力与魔法保持原值。" if result["ready"] else f"已记录休息，约{math.ceil(result['remaining']/60)}分钟后再点一次恢复情绪。体力与魔法由补给补充。")
            self._show_page("town")

    def _open_room_editor(self,selected=None,instance=None):
        if selected and selected not in product.CATALOG:
            selected,instance=None,None
        if selected and product.CATALOG[selected].get("kind") == "floor_upgrade":
            self._commit(lambda p: product.switch_floor(p, product.CATALOG[selected]["target_floor"]))
            selected = None
        self._room_selected,self._room_location,self._room_instance=selected,None,instance
        self._show_page("town",self._build_room_editor)

    def _home_floor_navigation(self, frame, *, editor=False):
        house = product.house_state(self.g)
        self._text(frame, f"我的家 · 当前{house['active_floor']}楼 · 共{house['unlocked_floors']}层 · 总空间{house['unlocked_floors']*32}格。每层独立装修，家具数量全屋共用。", bold=True, color=C["brand"])
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=5)
        self.home_floor_buttons = {}
        for floor in range(1, 4):
            unlocked = floor <= house["unlocked_floors"]
            title = f"{floor}楼" + (" · 当前" if house["active_floor"] == floor else "" if unlocked else " · 待扩建")
            button = btn_soft(row, text=title, width=140,
                command=lambda target=floor: self._switch_home_floor(target, editor) if target <= product.house_state(self.g)["unlocked_floors"] else self._show_page("shop", lambda:self._build_store("房间装修")))
            button.pack(side="left", padx=(0, 8))
            self.home_floor_buttons[floor] = button

    def _switch_home_floor(self, floor, editor=False):
        if self._commit(lambda p:product.switch_floor(p, floor)):
            self._open_room_editor() if editor else self._show_page("town")

    def _build_room_editor(self):
        frame,g=self._scroll(),self.g
        self._heading(frame,"布置我的家","选择物品，再点地面格子或墙面槽位预览，确认后保存。取消不改变原布置。")
        self._home_floor_navigation(frame, editor=True)
        self._home_scene=HomeScene(frame,self.sprites,g,on_select=self._preview_room_location)
        self._home_scene.pack(fill="x",pady=8)
        self._room_note=self._text(frame,"先从下面选一件已拥有的家装。")
        actions=ctk.CTkFrame(frame,fg_color="transparent")
        actions.pack(fill="x",pady=6)
        self._room_save=btn_primary(actions,text="保存这次布置",command=self._save_room,state="disabled")
        self._room_save.pack(side="left",padx=(0,8))
        btn_ghost(actions,text="取消预览",command=lambda:self._open_room_editor()).pack(side="left",padx=5)
        btn_ghost(actions,text="完成布置",command=lambda:self._show_page("town")).pack(side="left",padx=5)
        stock=product.state(g)["stock"]
        for identifier,count in stock.items():
            item=product.CATALOG.get(identifier)
            if count<=0 or not item or item["category"]=="消耗品" or item["kind"]=="floor_upgrade":
                continue
            row=self._card_frame(frame)
            row.pack(fill="x",pady=3)
            picture = self.sprites.market_icon(identifier, 65)
            ctk.CTkLabel(row, text="", image=picture).pack(side="left", padx=(14, 0), pady=8)
            detail = "已解锁 · 各层可反复应用" if item["kind"] in ("wallpaper", "floor") else f"拥有{count} · 全屋已放{product.placed_count(g,identifier)} · 可用{count-product.placed_count(g,identifier)}"
            self._text(row,f"{item['name']} · {detail}",size=12)
            btn_soft(row,text="选择 / 应用",height=29,command=lambda key=identifier:self._choose_room_item(key)).pack(side="left",padx=14,pady=(0,8))
            instances=[key for key,v in product.state(g)["room"]["placements"].items() if v["item"]==identifier]
            for instance in instances:
                btn_ghost(row,text="移动",height=29,width=65,command=lambda key=identifier,i=instance:self._choose_room_item(key,i)).pack(side="left",padx=3,pady=(0,8))
                btn_ghost(row,text="收回",height=29,width=65,command=lambda i=instance:self._remove_room_item(i)).pack(side="left",padx=3,pady=(0,8))
            for slot,placed in product.state(g)["room"]["wall"].items():
                if placed==identifier:
                    btn_ghost(row,text="收回墙面物品",height=29,command=lambda key=slot:self._remove_room_item(key)).pack(side="left",padx=3,pady=(0,8))
        btn_ghost(frame,text="恢复基础壁纸与地板",command=self._clear_room_style).pack(anchor="w",pady=9)
        if self._room_selected:
            self._choose_room_item(self._room_selected,self._room_instance)

    def _choose_room_item(self,identifier,instance=None):
        self._room_selected,self._room_instance,self._room_location=identifier,instance,None
        item=product.CATALOG.get(identifier)
        if item is None:
            self._room_note.configure(text='这件物品已不在目录中，请选择其他家装。')
            self._room_save.configure(state='disabled')
            return
        self._room_note.configure(text=item["name"]+"："+item["description"]+" 请选择位置。")
        self._home_scene.set_preview(identifier)
        self._room_save.configure(state="disabled")
        if item["kind"] in ("wallpaper","floor"):
            self._preview_room_location({})

    def _preview_room_location(self,location):
        if not self._room_selected:
            return
        item=product.CATALOG.get(self._room_selected)
        if item is None:
            self._room_save.configure(state='disabled')
            return
        if item["kind"]=="furniture" and "x" not in location or item["kind"]=="wall" and "slot" not in location:
            self._room_note.configure(text="请选择地面格子。" if item["kind"]=="furniture" else "请选择墙面槽位。")
            return
        self._room_location=location
        candidate={"game":{"product":{"stock":product.state(self.g)["stock"],"room":copy.deepcopy(product.state(self.g)["room"]),
                                         "house":copy.deepcopy(product.house_state(self.g))}}}
        try:
            product.place(candidate,self._room_selected,instance=self._room_instance,**location)
            valid=True
            self._room_note.configure(text="预览合法，点击保存即可放入。")
        except ValueError as error:
            valid=False
            self._room_note.configure(text=str(error))
        self._home_scene.set_preview(self._room_selected,location,valid=valid)
        self._room_save.configure(state="normal" if valid else "disabled")

    def _save_room(self):
        if self._room_selected and self._room_location is not None:
            if self._commit(lambda p:product.place(p,self._room_selected,instance=self._room_instance,**self._room_location)):
                self._open_room_editor()

    def _remove_room_item(self,instance):
        if self._commit(lambda p:product.remove_placement(p,instance)):
            self._open_room_editor()

    def _clear_room_style(self):
        if self._commit(lambda p:product.state(p["game"])["room"].update(wallpaper=None,floor=None)):
            self._open_room_editor()

    def _build_growth(self):
        frame,g=self._scroll(),self.g
        hero=product.active_hero(g)
        self._heading(frame,"成长与技能",f"Lv.{product.level(g)} · 总经验{g['xp']} · 体力上限{hero['maximum']/100:g}。升级只增加上限，当前体力由消耗品补充。")
        self._text(frame,"一级上限100点，每级增加5点，暂封顶250点；每个完整未上线日固定扣10点。角色体力分别保存。")
        for skill in product.CONFIG["skills"]:
            card=self._card_frame(frame)
            card.pack(fill="x",pady=6)
            self._text(card,f"{skill['name']} · Lv.{skill['level']}开放 · 消耗{skill['energy']}点体力",size=15,bold=True,color=C["brand"])
            self._text(card,skill["description"])
        btn_soft(frame,text="去背包使用补给",command=lambda:self._show_page("bag")).pack(anchor="w",pady=12)
        if any(key not in product.HEROES for key in g["inventory"]):
            btn_ghost(frame,text="旧版技能与奇物档案",command=lambda:self._show_page("growth",lambda:AdventureApp._build_growth(self))).pack(anchor="w",pady=7)

    def _build_tools(self):
        frame=self._scroll()
        self._heading(frame,"学习工具与设置","完整题型、统计、收藏和原有参考资料继续保留。")
        for label,builder in (("基础学习 · 完整书本/章节/题型筛选",lambda:App._build_home(self)),
                              ("学习统计",self._open_chapter_stats),("错题与学习记录",self._open_wrongbook),
                              ("收藏夹",self._open_favorites),("公式图鉴",self._build_finance_formulas),
                              ("旧版经营建筑与剧情",lambda:AdventureApp._build_finance_town(self))):
            btn_soft(frame,text=label,height=34,command=lambda b=builder:self._show_page("tools",b)).pack(fill="x",pady=4)
        variable=tk.BooleanVar(value=product.state(self.g)["settings"]["reduced_motion"])
        control=ctk.CTkCheckBox(frame,text="减少动画 · 保留静态表情和所有奖励",variable=variable,
                               command=lambda:self._change_motion(variable.get()),font=_f(12))
        control.pack(anchor="w",pady=14)
        settings=product.state(self.g)['settings']
        sound=tk.BooleanVar(value=settings.get('sound',True))
        ctk.CTkCheckBox(frame,text='精灵收服音乐与操作音效',variable=sound,font=_f(12),
                       command=lambda:self._change_audio(enabled=sound.get())).pack(anchor='w',pady=(0,10))
        self._audio_volume_label=ctk.CTkLabel(frame,text=f"音乐音量 {settings.get('volume',50)}%",font=_f(12))
        self._audio_volume_label.pack(anchor='w')
        volume=ctk.CTkSlider(frame,from_=0,to=100,number_of_steps=20,width=300,
                           command=lambda value:self._preview_audio_volume(round(value)))
        volume.set(settings.get('volume',50));volume.pack(anchor='w',pady=(5,14))
        volume.bind('<ButtonRelease-1>',lambda event:self._change_audio(volume=round(volume.get())),add='+')
        self._text(frame,"资料和进度保存在本机。原题事实和题号保留，必要图表采用简洁重绘；首次迁移会保留存档备份。",size=11)
        btn_ghost(frame,text="查看存档记录",height=30,command=lambda:self._show_page("saves")).pack(anchor="w",pady=12)

    def _preview_audio_volume(self, value):
        self._audio_volume_label.configure(text=f'音乐音量 {value}%')
        self._hunt_audio.configure(enabled=product.state(self.g)['settings'].get('sound',True), volume=value)
        self._hunt_sfx.configure(enabled=product.state(self.g)['settings'].get('sound',True), volume=value)

    def _change_audio(self, *, enabled=None, volume=None):
        def update(progress):
            settings=product.state(progress['game'])['settings']
            if enabled is not None: settings['sound']=bool(enabled)
            if volume is not None: settings['volume']=max(0,min(100,int(volume)))
        if self._commit(update):
            settings=product.state(self.g)['settings']
            self._hunt_audio.configure(enabled=settings.get('sound',True), volume=settings.get('volume',50))
        else:
            settings=product.state(self.g)['settings']
            self._hunt_audio.configure(enabled=settings.get('sound',True), volume=settings.get('volume',50))
        self._hunt_sfx.configure(enabled=settings.get('sound',True), volume=settings.get('volume',50))

    def _change_motion(self,value):
        if self._commit(lambda p:product.state(p["game"])["settings"].update(reduced_motion=bool(value))):
            self._show_page("tools")

    def _start_stage(self,stage_id,restart=False):
        if not stage_id.startswith("v5:"):
            return super()._start_stage(stage_id,restart)
        self._flush_draft()
        a=self._commit(lambda p:product.start_adventure(p,stage_id,restart=restart))
        if not a:
            return
        self._game_mode=True
        self.current_qids=list(a["qids"])
        self.current_idx=min(a["index"],len(a["qids"])-1)
        item=game.level_for(self.g,stage_id)
        self.current_mode="案例自评" if item["subjective"] else "章节擂主" if item["kind"]=="boss" else "冒险闯关"
        self._build_quiz()

    def _open_practice(self,attempt):
        self._game_mode=False
        self.current_qids=list(attempt["qids"])
        self.current_idx=min(attempt["index"],len(attempt["qids"])-1)
        self.current_mode=attempt["name"]
        self._practice_restart=False
        self._build_quiz()

    def _resume_practice(self):
        a=self.progress.get("practice")
        if not a or a["settled"]:
            return
        if a:
            try:
                product.require_action(self.g)
            except ValueError as error:
                messagebox.showinfo("伙伴休眠",str(error))
                return
        self._open_practice(a)

    def _start_qids(self,qids,mode="自选"):
        qids=list(dict.fromkeys(qid for qid in qids if qid in self.qmap))
        a=self._commit(lambda p:product.start_practice(p,qids,mode="basic",name=mode))
        if a:
            self._open_practice(a)

    def _attempt(self,progress=None):
        p=progress or self.progress
        return p["game"].get("active") if self._game_mode else p.get("practice")

    def _build_quiz(self):
        if not self.current_qids:
            return
        try:
            product.require_action(self.g)
        except ValueError as error:
            messagebox.showinfo('伙伴休眠', str(error))
            self._show_page('home')
            return
        if not self._game_mode:
            a=self.progress.get("practice")
            if not a or a.get("qids")!=self.current_qids or not a.get("product_mode") or a["settled"] or self._practice_restart:
                a=self._commit(lambda p:product.start_practice(p,self.current_qids,mode="basic",name=self.current_mode))
                if not a:
                    return
            self._practice_restart=False
        self._hide_sidebar()
        self._clear()
        self._practice_skills_enabled=not self._game_mode
        top=ctk.CTkFrame(self.page_area,fg_color="transparent")
        top.pack(fill="x",padx=22,pady=(12,3))
        btn_ghost(top,text="← 保存并返回",width=110,height=30,font=_f(11),command=self._back_home).pack(side="left")
        self.lbl_meta=ctk.CTkLabel(top,text="",font=_f(11),text_color=C["text_sub"])
        self.lbl_meta.pack(side="left",padx=10)
        self.btn_fav=btn_soft(top,text="☆ 收藏",width=76,height=30,font=_f(11),command=self._toggle_favorite_current)
        self.btn_fav.pack(side="right")
        score=ctk.CTkFrame(self.page_area,fg_color="transparent")
        score.pack(fill="x",padx=25,pady=2)
        self.lbl_score=ctk.CTkLabel(score,text="",font=_f(12,"bold"),text_color=C["brand"])
        self.lbl_score.pack(side="left")
        biome="forest"
        if self._game_mode:
            biome=game.level_for(self.g,self.g["active"]["stage_id"])["biome"]
        else:
            prefix=self.qmap[self.current_qids[0]].get("book_id","")
            biome="stars" if prefix.startswith("cg_original") else "island" if prefix.startswith("law_original") else "forest"
        a=self._attempt()
        self._quiz_map_expanded = False
        self._quiz_map_button = btn_ghost(top, text='地图全景', height=30, width=95, command=self._toggle_quiz_map)
        self._quiz_map_button.pack(side='right', padx=5)
        self._game_scene=AdventureScene(self.page_area,self.sprites,self.g,biome=biome,scene_id=a.get('scene_id') or world_scenes.question_scene(self.qmap[self.current_qids[0]]),height=180,boss=a.get("product_mode") in ("arena","arena_skills"),companions_snapshot=a.get('companions_snapshot'))
        self._game_scene.pack(fill="x",padx=25,pady=4)
        feedback=ctk.CTkFrame(self.page_area,fg_color="transparent")
        feedback.pack(fill="x",padx=25,pady=(0,3))
        self._quiz_feedback_text=ctk.CTkLabel(feedback,text="",font=_f(12),text_color=C["brand"],anchor="w",justify="left")
        self._quiz_feedback_text.pack(side="left",fill="x",expand=True)
        self._quiz_retry_button=btn_primary(feedback,text="重试保存",height=27,width=85,font=_f(10),command=self._retry_pending)
        self._early_end_button=btn_ghost(feedback,text="提前结束",height=26,width=85,font=_f(10),state='disabled',command=self._end_attempt_early)
        self._early_end_button.pack(side="right")
        self._build_quiz_mood(feedback)
        self.progress_bar=ctk.CTkProgressBar(self.page_area,height=6,corner_radius=100)
        self.progress_bar.pack(fill="x",padx=25,pady=(2,5))
        self._skill_controls=ctk.CTkFrame(self.page_area,fg_color="transparent")
        self._skill_controls.pack(fill="x",padx=25,pady=(0,4))
        self.body=ctk.CTkScrollableFrame(self.page_area,fg_color="transparent")
        self.body.pack(fill="both",expand=True,padx=22,pady=(0,10))
        # 只在进入答题时准备当前穿着的反馈表情，避免首几题临时合成精细衣帽。
        for pose in ("idle", "sleep", *product.CONFIG["feedback"]["correct"], *product.CONFIG["feedback"]["wrong"]):
            self.sprites.compose(self.g, pose)
        self._render_current()

    def _render_current(self):
        # 复用原题目渲染；新表情只绘制一次，避免旧版先画idle再重复重绘。
        App._render_current(self)
        if not self.current_qids or not self._game_scene:
            return
        qid=self.current_qids[self.current_idx]
        question=self.qmap[qid]
        a=self._attempt()
        number=question.get("source_ref",{}).get("original_question_number")
        if number:
            self.lbl_meta.configure(text=f"{self._chapter_label(question)} · {question['type']} · 原题号 {number} [{self.current_mode}]")
        self._render_skill_controls()

        if not store.is_subjective(question) and not self.answer_submitted:
            for letter in a.get("hints",{}).get(qid,[]):
                if letter in self.option_buttons:
                    self.option_buttons[letter].configure(state="disabled",text_color=C["text_sub"])
        if not question.get("subquestions"):
            for index,text in enumerate(a.get("outlines",{}).get(qid,[]),1):
                card=self._card_frame(self.body)
                card.pack(fill="x",pady=5)
                self._text(card,f"答题卡 {index} · {text}")
        self._refresh_quiz_product_status()

    def _toggle_quiz_map(self):
        if not self._game_scene or not self._game_scene.winfo_exists():
            return
        self._quiz_map_expanded = not self._quiz_map_expanded
        self._game_scene.overview = self._quiz_map_expanded
        self._game_scene.configure(height=340 if self._quiz_map_expanded else 180)
        self._quiz_map_button.configure(text='收起地图' if self._quiz_map_expanded else '地图全景')
        self._game_scene.redraw()

    def _refresh_quiz_product_status(self):
        qid=self.current_qids[self.current_idx]
        question=self.qmap[qid]
        a=self._attempt()
        reward=a.get("product_actions",{}).get(qid,{})
        feedback=reward.get("feedback")
        hero=product.active_hero(self.g)
        self._game_scene.g=self.g
        self._game_scene.boss=a.get("product_mode") in ("arena","arena_skills") or self._game_mode and game.level_for(self.g,a["stage_id"])["kind"]=="boss"
        pose="sleep" if hero["energy"]<=0 else feedback["pose"] if feedback else "think" if store.is_subjective(question) else "idle"
        self._game_scene.set_pose(pose)
        self._quiz_feedback_text.configure(text=self._feedback_line(reward) if feedback else f"体力 {hero['energy']/100:g}/{hero['maximum']/100:g} · 提交消耗0.2点"+(" · 体力为0，请还魂或重开" if hero["energy"]<=0 else ""))
        clue=a.get("product_clues",{}).get(qid)
        if clue and not self.answer_submitted:
            self._quiz_feedback_text.configure(text="回忆线索："+clue)
        if self.answer_submitted and hero["energy"]<=0 and a.get("product_mode") in ("adventure","arena","remediation") and self.current_idx<len(self.current_qids)-1:
            self.btn_next.configure(state="disabled",text="体力耗尽 · 先去补给")
        if not self.answer_submitted and hero["energy"]<=0 and a.get("product_mode") in ("adventure","arena","remediation"):
            self._quiz_feedback_text.configure(text="体力耗尽，草稿已保留。购买并使用还魂丹后继续本题。")
            if hasattr(self,"btn_submit") and self.btn_submit.winfo_exists():
                self.btn_submit.configure(state="disabled")

    def _feedback_line(self,reward):
        text=reward["feedback"]["text"]
        for key,label in (("xp","经验"),("coins","金币"),("materials","建材")):
            if key == 'coins' and reward.get('coin_credit'):
                text += f"  金币+{reward['coin_credit']}"
                continue
            if reward.get(key):
                text+=f"  {label}+{reward[key]}"
        if reward.get("self_assessed"):
            text+="  · 过程自评，单独记录"
        elif reward.get("assisted"):
            text+="  · 使用提示，不计独立掌握"
        if 'mood_after' in reward:
            delta = reward['mood_after'] - reward['mood_before']
            if delta:
                text += f"  情绪{delta:+d}"
        if reward.get('mood_energy') or reward.get('mood_mana'):
            text += f"  · 低落额外体力−{reward.get('mood_energy', 0):g} / 魔法−{reward.get('mood_mana', 0)}"
        return text

    def _render_score_only(self):
        if not self.current_qids:
            return
        a=self._attempt()
        answered=len(a["answers"])
        correct=sum(bool(rec["correct"]) for rec in a["answers"].values())
        hero=product.active_hero(self.g)
        text=f"第{self.current_idx+1}/{len(self.current_qids)}题 · 已答{answered} · 答对{correct} · 体力{hero['energy']/100:g}/{hero['maximum']/100:g}"
        if a.get("product_mode")=="arena":
            text+=f" · NPC目标{a['target']}题"
        elif self._game_mode:
            # 提示线与结算线同源：Boss/挑战关读 attempt 冻结的规则快照，成长模式经典关按 80%（与 desktop_growth 结算一致）。
            percent=(a.get('challenge_rules') or {}).get('pass_percent')
            if not percent:
                if a["stage_id"].startswith("v5:") or a.get("ruleset")=="5.2.0":
                    percent=product.CONFIG["pass_percent"]
                elif a.get("ruleset")=="5.3.0":
                    percent=80
                else:
                    percent=game.CONFIG["pass_percent"]
            text+=f" · {math.ceil(len(a['qids'])*percent/100)}题可通关"
        self.lbl_score.configure(text=text)
        self.progress_bar.set(answered/len(self.current_qids))
        button = getattr(self, '_early_end_button', None)
        if button is not None and button.winfo_exists():
            status = product.early_end_status(a) if self._game_mode else {'allowed': False}
            button.configure(state='normal' if status['allowed'] and not self._pending_transaction else 'disabled')

    def _end_attempt_early(self):
        if self._pending_transaction or not self._game_mode:
            return
        self._flush_draft()
        if self._pending_transaction:
            return
        status = product.early_end_status(self._attempt())
        if not status['allowed']:
            return
        if not messagebox.askyesno('提前结束本关', status['reason'] + '\n\n本关将按未通关结算。已答成绩和奖励保留，未答题不会扣体力或计入错题本。也可以继续练习。\n要提前结束吗？'):
            return
        result = self._commit(product.end_adventure_early)
        if result:
            self._show_result(result)

    def _render_skill_controls(self):
        if not hasattr(self,"_skill_controls") or not self._skill_controls.winfo_exists() or not self.current_qids:
            return
        buttons=getattr(self,'_product_skill_buttons',{})
        reuse=bool(buttons) and all(button.winfo_exists() and button.master is self._skill_controls for button in buttons.values())
        if not reuse:
            for widget in self._skill_controls.winfo_children():widget.destroy()
            buttons={};self._product_skill_buttons=buttons
        q=self.qmap[self.current_qids[self.current_idx]]
        a=self._attempt()
        for identifier,skill in product.SKILLS.items():
            key=identifier+(":"+q["id"] if identifier=="recall" else "")
            button=buttons.get(identifier)
            if button is None:
                button=btn_soft(self._skill_controls,text=f"{skill['name']} · {skill['energy']}体力",height=28,font=_f(10),
                            command=lambda sid=identifier:self._use_product_skill(sid))
                button.pack(side="left",padx=(0,7));buttons[identifier]=button
            disabled=self.answer_submitted or product.level(self.g)<skill["level"] or key in a.get("product_skills",[]) or product.active_hero(self.g)["energy"]<skill["energy"]*100
            button.configure(state='disabled' if disabled else 'normal')

    def _use_product_skill(self,identifier):
        q=self.qmap[self.current_qids[self.current_idx]]
        result=self._commit(lambda p:product.use_skill(p,identifier,q,practice=not self._game_mode))
        if result:
            self._render_current()
            self._quiz_feedback_text.configure(text=result)

    def _submit_answer(self):
        if not self.current_qids or self.answer_submitted:
            return
        q=self.qmap[self.current_qids[self.current_idx]]
        if store.is_subjective(q):
            return
        answer=self.current_judge if q["type"]=="判断题" else "".join(sorted(self.current_selection))
        if not answer:
            return
        correct=is_correct(q,answer)
        def submit(p):
            if self._game_mode:
                return game.submit_answer(p,q,answer,correct)
            return product.submit_practice(p,q,answer,correct)
        if self._commit(submit):
            self._after_product_answer()

    def _after_product_answer(self):
        qid=self.current_qids[self.current_idx]
        reward=self._attempt().get("product_actions",{}).get(qid,{})
        if reward.get("feedback"):
            self._game_scene.g=self.g
            self._game_scene.pulse(reward["feedback"]["pose"])
        question=self.qmap[qid]
        if store.is_subjective(question):
            if question.get('subquestions') and self._refresh_finance_grade(question):
                self._render_score_only()
                for button in self._skill_controls.winfo_children():
                    if isinstance(button, ctk.CTkButton):
                        button.configure(state='disabled')
                self._refresh_quiz_product_status();self._scroll_answer_feedback()
                return
            self._render_current()
            return
        # 客观题只更新提交结果；保留题干、选项及布局，避免整页销毁/重排。
        record=self._attempt()["answers"][qid]
        user_answer=record.get("user_answer", "")
        self.answer_submitted=True
        if question["type"]=="判断题":
            self.current_judge=user_answer
        else:
            self.current_selection=set(user_answer.upper())
        for button in self.option_buttons.values():
            if button.cget('state') != 'normal':
                button.configure(state="normal")
        self._highlight_options(question,user_answer)
        self._render_explanation_objective(question,user_answer,record.get("correct",False))
        self._update_action_buttons_objective()
        self._render_score_only()
        for button in self._skill_controls.winfo_children():
            if isinstance(button, ctk.CTkButton):
                button.configure(state="disabled")
        self._refresh_quiz_product_status()
        self._scroll_answer_feedback()

    def _self_mark(self,correct):
        if not self.current_qids or self.answer_submitted:
            return
        q=self.qmap[self.current_qids[self.current_idx]]
        answer=self.user_answer_box.get("1.0","end").strip()
        if not answer:
            return
        def mark(p):
            a=self._attempt(p)
            if q["id"] not in a["references"]:
                raise ValueError("请先查看参考答案，再对照自评。")
            if self._game_mode:
                return game.submit_answer(p,q,answer,correct)
            return product.submit_practice(p,q,answer,correct)
        if self._commit(mark):
            self._after_product_answer()

    def _finance_grade(self):
        q=self._finance_question()
        def grade(p):
            a=self._finance_attempt(p)
            result=finance.grade(a,q)
            if result["first"]:
                rec=result["record"]
                reward=product.record_action(p,q,rec["correct"],rec["user_answer"],a,
                    mode="adventure" if self._game_mode else a.get("product_mode","basic"),self_assessed=True)
                a["answers"][q["id"]].update(assisted=reward["assisted"],self_assessed=True)
                if product.growth.current(a):
                    from desktop_growth import stamp_answer
                    stamp_answer(a,q['id'])
            return result
        if self._commit(grade):
            self._after_product_answer()

    def _next_q(self):
        if (self.current_qids and not store.is_subjective(self.qmap[self.current_qids[self.current_idx]])
                and getattr(self, '_objective_layout_body', None) is getattr(self, 'body', None)
                and getattr(self, '_objective_layout_roots', ())
                and not self._objective_layout_is_live()):
            # 保存会处理界面消息；先修复受损旧卡，避免等待期间调用死滚动条。
            self._render_current()
        self._flush_draft()
        if self._pending_transaction:
            return
        if not self.current_qids:
            return
        a=self._attempt()
        if self.current_qids[self.current_idx] not in a["answers"]:
            return
        if product.death_locked(self.g):
            messagebox.showinfo('体力耗尽', '当前成绩已保存。请先还魂，或重新开始整个游戏。')
            self._show_page('home')
            return
        if self.current_idx==len(self.current_qids)-1:
            result=self._commit(lambda p:game.settle_attempt(p) if self._game_mode else product.settle_practice(p))
            if result:
                if self._game_mode:
                    self._show_result(result)
                elif result.get("adventure_result"):
                    self._show_result(result["adventure_result"])
                else:
                    self._show_practice_result(result)
            return
        if product.active_hero(self.g)["energy"]<=0:
            messagebox.showinfo("体力耗尽","已提交成绩和奖励保留。请购买并使用还魂丹，再继续本次挑战。")
            return
        index=self.current_idx+1
        if self._commit(lambda p:self._attempt(p).update(index=index)):
            self.current_idx=index
            self._render_current()

    def _prev_q(self):
        self._flush_draft()
        if self.current_idx>0 and self._commit(lambda p:self._attempt(p).update(index=self.current_idx-1)):
            self.current_idx-=1
            self._render_current()

    def _redo_current(self):
        if self.current_qids:
            qid=self.current_qids[self.current_idx]
            self._start_qids([qid],"重做练习 · 首次成绩保留")

    def _back_home(self):
        self._flush_draft()
        if self._pending_transaction:
            return
        kind=self._attempt().get("product_mode") if self.current_qids and self._attempt() else "adventure"
        self.current_qids=[]
        self._game_mode=False
        self._show_page("practice" if kind in ("arena","arena_skills") else "town" if kind=="review" else "home")

    def _show_result(self,result):
        if not result["stage_id"].startswith("v5:"):
            return super()._show_result(result)
        self.current_qids=[]
        self._game_mode=False
        def build():
            frame,g=self._scroll(),self.g
            item=game.level_for(g,result["stage_id"])
            self._heading(frame,"地图又亮了一点！" if result["passed"] else "先补练，再继续探险",item["chapter_title"]+" · "+item["name"])
            scene=AdventureScene(frame,self.sprites,g,biome=item["biome"],scene_id=g['active'].get('scene_id') or world_scenes.stage_scene(g,item['id']),height=185,pose="celebrate" if result["passed"] else "sad",companions_snapshot=result.get('companions_snapshot'))
            scene.pack(fill="x",pady=8)
            card=self._card_frame(frame)
            card.pack(fill="x",pady=7)
            self._text(card,f"首答 {result['correct']}/{result['total']} · 正确率{result['correct']/result['total']:.0%}  "+"★"*result["stars"],size=20,bold=True,color=C["brand"])
            self._text(card,f"本次结算：经验+{result['xp']} · 金币+{result['coins']} · 建材+{result['materials']}")
            if result.get("self_assessed"):
                self._text(card,"案例过程含自评，记录为案例完成；不冒充客观独立判分，最多一星。",size=11)
            if result.get("remediation"):
                self._text(card,"补练完成后点亮本关，原首答成绩保持不变。",size=11)
            if result.get('requires_boss_retry'):
                self._text(card,"错题已补练。Boss需重新完整挑战并达到90%才能通关。",size=12)
            if result["level_after"]>result["level_before"]:
                self._text(card,f"升级 Lv.{result['level_before']} → Lv.{result['level_after']}！体力上限增加，当前体力未补充。",bold=True,color=C["brand"])
            if result["passed"]:
                target=product.next_stage(g,result["stage_id"])
                btn_primary(frame,text="进入下一关 →" if target else "本世界已完成 · 返回地图",height=41,
                            command=lambda:self._start_stage(target) if target else self._show_page("home")).pack(fill="x",pady=7)
            else:
                if not result.get('requires_boss_retry') and not result.get('early_end'):
                    btn_primary(frame,text="补练本关错题 →",height=41,command=lambda:self._start_remediation(result)).pack(fill="x",pady=7)
                btn_soft(frame,text="重新完整挑战",command=lambda:self._start_stage(result["stage_id"],restart=True)).pack(fill="x",pady=5)
            if result["wrong_qids"]:
                btn_ghost(frame,text="查看本轮错题与解析",command=lambda:self._review_result(result)).pack(fill="x",pady=5)
            btn_ghost(frame,text="返回章节地图",command=lambda:self._open_chapter(item["chapter_id"])).pack(fill="x",pady=5)
        self._show_page("home",build)

    def _start_remediation(self,result):
        a=self._commit(lambda p:product.start_practice(p,result["wrong_qids"],mode="remediation",name="关卡补练 · 原首答成绩保留",parent_attempt_id=result["attempt_id"]))
        if a:
            self._open_practice(a)

    def _show_practice_result(self,result):
        self.current_qids=[]
        self._game_mode=False
        def build():
            frame=self._scroll()
            title="比武结束 · "+result["outcome"] if result["outcome"] else "练习完成，进步已记下"
            self._heading(frame,title,result["name"])
            card=self._card_frame(frame)
            card.pack(fill="x",pady=10)
            label=f"独立答对 {result['independent_correct']}/{result['total']} · NPC目标{result['target']}" if result["mode"]=="arena" else f"游戏计分 {result['game_correct']}/{result['total']} · NPC目标{result['target']} · 技能娱乐挑战" if result['mode']=='arena_skills' else f"正确 {result['correct']}/{result['total']}"
            self._text(card,label,size=20,bold=True,color=C["brand"])
            if result.get("self_assessed"):
                self._text(card,"含案例过程自评，单独记录，不计入客观独立掌握。",size=11)
            if result["mode"] in ("arena","arena_skills"):
                self._text(card,f"比武结算经验+{result.get('settlement_xp',result['xp'])}。两种模式共用同学科每日最佳结果补差，基础奖励最多20经验，装备加成另计。")
            self._text(card,"逐题奖励已保存；重新查看结算不会重复领奖。")
            if result.get("remediation_remaining"):
                btn_primary(frame,text="继续补练剩余错题",command=lambda:self._continue_remediation(result)).pack(fill="x",pady=8)
            btn_primary(frame,text="去经营小镇复习 / 装家",command=lambda:self._show_page("town")).pack(fill="x",pady=7)
            btn_soft(frame,text="再选重难点切磋",command=lambda:self._show_page("practice")).pack(fill="x",pady=5)
            btn_ghost(frame,text="返回冒险地图",command=lambda:self._show_page("home")).pack(fill="x",pady=5)
        self._show_page("practice",build)

    def _continue_remediation(self,result):
        previous=self.progress["practice"]
        qids=result["remediation_remaining"]
        parent=previous["parent_attempt_id"]
        a=self._commit(lambda p:product.start_practice(p,qids,mode="remediation",name="继续错题补练",parent_attempt_id=parent))
        if a:
            self._open_practice(a)

    def _commit(self,mutate):
        self._last_interaction_at=time.monotonic()
        result=super()._commit(mutate)
        if self._pending_transaction:
            for name in ('btn_submit', 'btn_next', 'btn_prev', 'btn_redo', 'btn_fav', '_early_end_button', 'user_answer_box'):
                widget = getattr(self, name, None)
                if widget is not None and widget.winfo_exists():
                    widget.configure(state='disabled')
            for widget in getattr(self, 'option_buttons', {}).values():
                if widget.winfo_exists():
                    widget.configure(state='disabled')
            controls = getattr(self, '_skill_controls', None)
            if controls is not None and controls.winfo_exists():
                for widget in controls.winfo_children():
                    if isinstance(widget, ctk.CTkButton):
                        widget.configure(state='disabled')
            button=getattr(self,"_quiz_retry_button",None)
            if button and button.winfo_exists():
                button.pack(side="right",padx=6)
            if self.current_qids and hasattr(self,"_quiz_feedback_text") and self._quiz_feedback_text.winfo_exists():
                self._quiz_feedback_text.configure(text="本次变更尚未保存，请点击「重试保存」。结果已暂存。")
        return result

    def _retry_pending(self):
        if waiting(self):return
        if not self._pending_transaction:
            return
        candidate,result=self._pending_transaction
        if not save_with_events(self,store.save_progress,candidate):
            messagebox.showerror("仍未保存","请检查存档目录权限和磁盘空间，暂存的同一结果仍保留。")
            return
        self.progress=candidate
        self._pending_transaction=None
        self.retry_save_btn.pack_forget()
        button=getattr(self,"_quiz_retry_button",None)
        if button and button.winfo_exists():
            button.pack_forget()
        self._sync_avatar()
        if self._market_pending_action:
            context = self._market_pending_action
            self._market_pending_action = None
            context["saved_at"] = time.perf_counter()
            self._market_after_saved(result, context)
            return
        if isinstance(result,dict) and "passed" in result:
            self._show_result(result)
        elif isinstance(result,dict) and result.get("adventure_result"):
            self._show_result(result["adventure_result"])
        elif isinstance(result,dict) and "outcome" in result:
            self._show_practice_result(result)
        elif self.current_qids and self._quiz_visible:
            a=self._attempt()
            if not a:
                self.current_qids=[]
                self._show_page(self._product_page)
                return
            self.current_idx=min(a["index"],len(self.current_qids)-1)
            self._render_current()
        else:
            self._show_page(self._product_page)

    def _on_reset(self):
        if not messagebox.askyesno("开始新游戏","先保存当前局，再从欢迎界面开启全新游戏。作答、错题、收藏、角色、技能、背包和家园从初始状态开始；存档记录最多保留两局，已有两局时替换较早的存档点。现在开始新游戏吗？"):
            return
        def reset(p):
            theme,scaling=p.get("theme","system"),p.get("scaling",1.0)
            p.clear()
            p.update(store.default_progress())
            p.update(theme=theme,scaling=scaling)
            p['reset_epoch'] = uuid.uuid4().hex
            game.ensure_game(p,self.questions)
            product.initialize(p,self.questions,legacy=False)
            return {"flow":"saves","operation":"restart"}
        if self._commit(reset):
            self.current_qids=[]
            self._game_mode=False
            self._show_page("home")

    def _on_clear_wrongbook(self):
        scope="当前书本的" if self.current_book_id else "全部"
        if not messagebox.askyesno("清空错题本",f"清空{scope}错题与待巩固列表？答题历史和已获得奖励保留。"):
            return
        identifiers={qid for qid in self.progress["wrong_book"] if not self.current_book_id or self.current_book_id in self.qmap.get(qid,{}).get("book_ids", [self.qmap.get(qid,{}).get("book_id")])}
        def clear(p):
            p["wrong_book"]=[qid for qid in p["wrong_book"] if qid not in identifiers]
            for qid in identifiers:
                review=product.state(p["game"])["reviews"].get(qid)
                if review:
                    # 保留发奖窗口，防止清空后重建错题重复领建材。
                    review["status"]="已移出"
        if self._commit(clear):
            self._show_page("wrongbook",self._open_wrongbook)

    def destroy(self):
        if defer_close(self):return
        self._closing_app = True
        if hasattr(self, "sprites"):
            self.sprites.close()
        try:
            release_resources(self)
            super().destroy()
        finally:
            self._gui_gc.close()


from desktop_growth_ui import GrowthUIMixin
from desktop_hunting_ui import HuntingUIMixin
from desktop_save_ui import SaveUIMixin
from desktop_journey_ui import JourneyUIMixin


class GrowthProductApp(JourneyUIMixin, HuntingUIMixin, GrowthUIMixin, SaveUIMixin, ProductApp):
    _pages = {**ProductApp._pages, 'workshop': '_build_workshop', 'roles':'_build_roles','hunting':'_build_hunting','suits':'_build_suits','saves':'_build_save_records','restart':'_build_restart_game'}

    def __init__(self):
        # 登录保存会服务窗口消息；所有混入层初始化完毕后才执行关窗。
        self._initializing_app = True
        self._close_after_initialization = False
        try:
            super().__init__()
        finally:
            self._initializing_app = False
        if self._close_after_initialization and self.winfo_exists():
            self._close_after_initialization = False
            self.after_idle(self._on_close)

    def _on_close(self):
        if self._initializing_app:
            self._close_after_initialization = True
            return
        return super()._on_close()


ProductApp = GrowthProductApp
