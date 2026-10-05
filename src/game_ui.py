"""小圆冒险桌面界面：沿用既有题目渲染与学习功能。"""
from __future__ import annotations

import copy
import ctypes
import math
import os
import hashlib
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import app as classic
import game
import game_skills as skills
import game_shop as shop
import store
import finance
from finance_ui import FinanceUIMixin
from app import App, C, _f, btn_ghost, btn_primary, btn_soft, is_correct
from game_art import AdventureScene, SpriteLibrary


class AdventureApp(FinanceUIMixin, App):
    def __init__(self) -> None:
        self._game_mode = False
        self._game_scene = None
        self._pending_transaction = None
        self._draft_timer = None
        self._shop_tab = "金币商店"
        self._shop_filter = "all"
        self._shop_detail = None
        self._growth_migration_pending = False
        self._practice_skills_enabled = False
        self._practice_restart = False
        self.sprites = SpriteLibrary()
        super().__init__()
        if self.winfo_exists():
            self.title(f"{classic.APP_TITLE} {classic.APP_VERSION}")
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            if self._growth_migration_pending:
                self._commit(lambda p: game.ensure_game(p, self.questions))
                self._growth_migration_pending = False

    @property
    def g(self) -> dict:
        existing = self.progress.get("game")
        if (not isinstance(existing, dict) or existing.get("growth_version") != 2
                or not existing.get("finance_expansion") or "xiaobao" not in existing.get("inventory", [])
                or existing.get("campaign", {}).get("bank_fingerprint") != game.build_campaign(self.questions)["bank_fingerprint"]):
            self._growth_migration_pending = True
        return game.ensure_game(self.progress, self.questions)

    def _commit(self, mutate):
        """先在副本中变更，写盘成功后替换内存，抽奖未保存不展示。"""
        if self._pending_transaction:
            messagebox.showinfo("还有待保存的进度", "请先点击侧栏「重试保存」，再继续操作。")
            return None
        candidate = copy.deepcopy(self.progress)
        try:
            result = mutate(candidate)
        except (ValueError, KeyError) as error:
            messagebox.showinfo("小圆提醒", str(error))
            return None
        if not store.save_progress(candidate):
            self._pending_transaction = (candidate, result)
            self.retry_save_btn.pack(fill="x", padx=16, pady=4)
            messagebox.showerror("保存失败", "磁盘写入失败，当前变更尚未生效。\n请检查磁盘空间或目录权限，再点击侧栏「重试保存」。\n奖励结果已暂存，不会重新抽取。")
            return None
        self.progress = candidate
        self._sync_avatar()
        return result if result is not None else True

    def _retry_pending(self) -> None:
        if not self._pending_transaction:
            return
        candidate, result = self._pending_transaction
        if not store.save_progress(candidate):
            messagebox.showerror("仍未保存", "无法写入存档，请检查磁盘空间与目录权限。")
            return
        self.progress = candidate
        self._sync_avatar()
        self._pending_transaction = None
        self.retry_save_btn.pack_forget()
        self.current_qids = []
        self._game_mode = False
        if isinstance(result, dict) and "passed" in result:
            self._show_result(result)
        else:
            self._show_page("home")

    def _save(self) -> None:
        if self._pending_transaction:
            messagebox.showinfo("尚未保存", "请先重试保存待处理进度。")
            return
        if self._practice_skills_enabled and self.current_qids:
            a = self.progress.get("practice")
            qid = self.current_qids[self.current_idx]
            if a and qid in a["qids"]:
                a["index"] = self.current_idx
        if not store.save_progress(self.progress):
            messagebox.showerror("保存失败", "学习记录暂未写入磁盘，请检查存档目录权限或磁盘空间。")

    def _clear(self) -> None:
        if self._draft_timer:
            try:
                self.after_cancel(self._draft_timer)
            except tk.TclError:
                pass
            self._draft_timer = None
        self._game_scene = None
        self._practice_skills_enabled = False
        # CustomTkinter 5.2.2 的下拉菜单 destroy 未注销缩放回调。
        # 页面销毁前补齐注销，避免切页后调整缩放或跨屏时访问已销毁菜单。
        from customtkinter.windows.widgets.scaling import CTkScalingBaseClass
        def release_menus(widget):
            for child in widget.winfo_children():
                release_menus(child)
            if isinstance(widget, tk.Menu) and isinstance(widget, CTkScalingBaseClass):
                CTkScalingBaseClass.destroy(widget)
        release_menus(self.page_area)
        super()._clear()

    def _build_sidebar(self) -> None:
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=15, pady=(18, 12))
        self.avatar_label = ctk.CTkLabel(brand, text="", image=self.sprites.portrait(self.g, 60))
        self.avatar_label.pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(brand, text="小圆冒险世界", font=_f(18, "bold"), text_color=C["brand"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="每一步，都有新地图", font=_f(11), text_color=C["text_sub"]).pack(anchor="w", pady=(4, 0))
        self.nav_btns = {}
        entries = [
            ("home", "冒险地图", self._build_home),
            ("practice", "自由刷题", self._build_practice),
            ("town", "经营小镇", self._build_finance_town),
            ("training", "章节训练", self._open_training),
            ("bag", "背包与商店", self._build_bag),
            ("growth", "成长与技能", self._build_growth),
            ("collection", "收藏图鉴", self._build_collection),
            ("wrongbook", "错题本", self._open_wrongbook),
            ("favorites", "收藏夹", self._open_favorites),
            ("stats", "学习统计", self._open_chapter_stats),
        ]
        symbols = ("◇", "▤", "⌂", "◈", "▣", "✧", "☆", "↺", "★", "▥")
        for (key, label, builder), symbol in zip(entries, symbols):
            button = ctk.CTkButton(self.sidebar, text=f"{symbol}   {label}", anchor="w", height=37,
                corner_radius=11, font=_f(13), fg_color="transparent", hover_color=C["side_hover"],
                text_color=C["text"], command=lambda k=key, b=builder: self._navigate(k, b))
            button.pack(fill="x", padx=13, pady=3)
            self.nav_btns[key] = button
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=14, pady=12)
        self.retry_save_btn = btn_primary(footer, text="重试保存", command=self._retry_pending, height=32)
        theme = ctk.CTkSegmentedButton(footer, values=["浅色", "深色", "系统"], command=self._on_theme_change, font=_f(11))
        self.theme_control = theme
        theme.pack(fill="x", pady=4)
        theme.set({"light": "浅色", "dark": "深色", "system": "系统"}.get(self.progress.get("theme"), "系统"))
        btn_ghost(footer, text="重置全部进度", command=self._on_reset, height=29, font=_f(10)).pack(fill="x", pady=4)
        ctk.CTkLabel(footer, text=f"{classic.APP_VERSION} · 离线冒险版", font=_f(10), text_color=C["text_sub"]).pack(anchor="w", pady=(5, 0))

    def _sync_avatar(self) -> None:
        if hasattr(self, "avatar_label") and self.avatar_label.winfo_exists():
            self.avatar_label.configure(image=self.sprites.portrait(self.g, 60))

    def _navigate(self, key: str, builder) -> None:
        self._flush_draft()
        self.current_qids = []
        self._game_mode = False
        self._show_page(key, builder)

    def _scroll(self) -> ctk.CTkScrollableFrame:
        frame = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=15)
        return frame

    def _heading(self, parent, title: str, subtitle: str = "") -> None:
        ctk.CTkLabel(parent, text=title, font=_f(24, "bold"), text_color=C["text"], anchor="w").pack(fill="x", pady=(0, 4))
        if subtitle:
            ctk.CTkLabel(parent, text=subtitle, font=_f(12), text_color=C["text_sub"], anchor="w",
                         wraplength=780, justify="left").pack(fill="x", pady=(0, 14))

    def _card_frame(self, parent, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=C["card"], border_color=C["border"], border_width=1,
                            corner_radius=17, **kwargs)

    def _build_home(self) -> None:
        self._game_mode = False
        g = self.g
        frame = self._scroll()
        st = game.stats(g)
        title = game.CATALOG.get(g.get("title"), {}).get("name", "新的冒险，等你出发")
        self._heading(frame, f"小圆，今天去哪里冒险？", f"Lv.{st['level']}  ·  {title}  ·  {game.CONFIG['pass_percent']}% 解锁下一关，{game.CONFIG['two_star_percent']}% 高质量通关")
        numbers = ctk.CTkFrame(frame, fg_color="transparent")
        numbers.pack(fill="x", pady=(0, 14))
        values = [("已通关", f"{st['cleared']} / {st['total']}"), ("冒险星星", str(st["stars"])),
                  ("成长经验", str(g["xp"])), ("金币", str(g["coins"]))]
        for column, (label, value) in enumerate(values):
            numbers.grid_columnconfigure(column, weight=1)
            card = self._card_frame(numbers)
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 7, 0))
            ctk.CTkLabel(card, text=label, font=_f(11), text_color=C["text_sub"]).pack(anchor="w", padx=16, pady=(10, 2))
            ctk.CTkLabel(card, text=value, font=_f(22, "bold"), text_color=C["brand"]).pack(anchor="w", padx=16, pady=(0, 10))
        worlds = ctk.CTkFrame(frame, fg_color="transparent")
        worlds.pack(fill="x", pady=(0, 12))
        for world in g["campaign"]["worlds"]:
            factory = btn_primary if world["id"] == g["world"] else btn_soft
            factory(worlds, text=world["name"], height=38, font=_f(14, "bold"),
                    command=lambda wid=world["id"]: self._switch_world(wid)).pack(side="left", padx=(0, 9))
        btn_ghost(worlds, text="无尽远征" if game.expedition_available(g) else "远征 · 通关后开启", height=38,
                  command=self._start_expedition).pack(side="right")
        world = next(w for w in g["campaign"]["worlds"] if w["id"] == g["world"])
        sid = game.next_stage(g, world_id=g["world"])
        level = game.level_for(g, sid)
        self._game_scene = AdventureScene(frame, self.sprites, g, biome=level["biome"], height=210)
        self._game_scene.pack(fill="x", pady=(0, 10))
        action = self._card_frame(frame)
        action.pack(fill="x", pady=(0, 18))
        text = ctk.CTkFrame(action, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=18, pady=12)
        ctk.CTkLabel(text, text=level["chapter_title"], font=_f(15, "bold"), text_color=C["text"],
                     anchor="w", wraplength=480, justify="left").pack(fill="x")
        ctk.CTkLabel(text, text=f"下一站：{level['name']} · {len(level['qids'])} 题", font=_f(11),
                     text_color=C["text_sub"], anchor="w").pack(fill="x", pady=(4, 0))
        btn_primary(action, text="继续冒险  →", height=43, width=142, font=_f(13, "bold"),
                    command=lambda: self._start_stage(sid)).pack(side="right", padx=16)
        active = g.get("active")
        if active and not active["settled"]:
            btn_soft(frame, text=f"恢复未完成挑战 · 已答 {len(active['answers'])}/{len(active['qids'])}", height=35,
                     command=lambda: self._start_stage(active["stage_id"])).pack(fill="x", pady=(0, 12))
        growth_row = self._card_frame(frame)
        growth_row.pack(fill="x", pady=(0, 14))
        next_skill = next((s for s in skills.view(g) if not s["unlocked"]), None)
        growth_text = (f"再积累 {next_skill['xp_remaining']} 经验 · Lv.{next_skill['level']} 学会「{next_skill['name']}」"
                       if next_skill else "全部技能已学会 · 用技能与奇物一起闯关")
        ctk.CTkLabel(growth_row, text=growth_text, font=_f(12, "bold"), text_color=C["brand"],
                     anchor="w", wraplength=570).pack(side="left", padx=16, pady=15)
        btn_soft(growth_row, text="查看成长 →", width=120, height=32,
                 command=lambda: self._show_page("growth")).pack(side="right", padx=14)
        self._heading(frame, "章节地图", world["subtitle"])
        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x")
        for column in (0, 1):
            grid.grid_columnconfigure(column, weight=1, uniform="chapters")
        for index, chapter in enumerate(world["chapters"]):
            card = self._card_frame(grid)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 7) if index % 2 == 0 else (7, 0), pady=6)
            biome = next(b for b in game.BIOMES if b["id"] == chapter["biome"])
            available = game.can_play(g, chapter["stages"][0])
            completed = sum(game.cleared(g, item) for item in chapter["stages"])
            ctk.CTkLabel(card, text=biome["name"], font=_f(10, "bold"), text_color=biome["color"],
                         anchor="w").pack(fill="x", padx=14, pady=(12, 3))
            ctk.CTkLabel(card, text=chapter["title"], font=_f(12, "bold"), text_color=C["text"],
                         wraplength=340, justify="left", anchor="w").pack(fill="x", padx=14)
            ctk.CTkLabel(card, text=f"已完成 {completed}/{len(chapter['stages'])} 关" if available else "完成上一章全部 Boss 后解锁",
                         font=_f(10), text_color=C["text_sub"], anchor="w").pack(fill="x", padx=14, pady=(5, 7))
            button = btn_soft(card, text="进入地图" if available else "尚未解锁", height=30, font=_f(11),
                    command=lambda ch=chapter: self._open_chapter(ch["id"]))
            button.pack(fill="x", padx=14, pady=(0, 12))
            if not available:
                button.configure(state="disabled")

    def _switch_world(self, world_id: str) -> None:
        if self._commit(lambda p: p["game"].update(world=world_id)):
            self._show_page("home")

    def _open_chapter(self, chapter_id: str) -> None:
        def build():
            g = self.g
            chapter = next(ch for w in g["campaign"]["worlds"] for ch in w["chapters"] if ch["id"] == chapter_id)
            frame = self._scroll()
            btn_ghost(frame, text="← 世界地图", height=30, command=lambda: self._show_page("home")).pack(anchor="w", pady=(0, 10))
            self._heading(frame, chapter["title"], "沿着路径前进。普通关每关 10 题，章节末尾是 Boss 与首次掉落宝箱。")
            nodes = []
            for sid in chapter["stages"]:
                level = game.level_for(g, sid)
                nodes.append({"id": sid, "kind": level["kind"], "cleared": game.cleared(g, sid),
                              "available": game.can_play(g, sid), "stars": g["results"].get(sid, {}).get("best_stars", 0)})
            height = 130 + math.ceil(len(nodes) / 4) * 105
            self._game_scene = AdventureScene(frame, self.sprites, g, biome=chapter["biome"], height=height,
                                               nodes=nodes, on_node=self._start_stage)
            self._game_scene.pack(fill="x", pady=(0, 15))
            self._game_scene.walk_to_current()
            for sid in chapter["stages"]:
                level = game.level_for(g, sid)
                row = self._card_frame(frame)
                row.pack(fill="x", pady=4)
                text = ("Boss · " if level["kind"] == "boss" else "") + level["name"]
                if level["kind"] == "boss":
                    loot = f"首次胜利有 {game.CONFIG['drop_percent']}% 额外掉落" if not game.cleared(g, sid) else "首次宝箱已结算，可继续刷星"
                    text += "  ·  " + loot
                status = " · 高质量通关" if g["results"].get(sid, {}).get("best_stars", 0) >= 2 else ""
                ctk.CTkLabel(row, text=f"{text}\n{len(level['qids'])} 题 · {game.CONFIG['pass_percent']}% 通关{status}", font=_f(12),
                             text_color=C["text"], anchor="w", justify="left", wraplength=560).pack(side="left", padx=15, pady=12)
                button = btn_primary(row, text="重玩" if game.cleared(g, sid) else "挑战", height=32, width=88,
                    command=lambda target=sid: self._start_stage(target))
                button.pack(side="right", padx=14)
                if not game.can_play(g, sid):
                    button.configure(state="disabled")
        self._show_page("home", build)

    def _build_practice(self) -> None:
        self._game_mode = False
        App._build_home(self)

    def _on_theme_change(self, value: str) -> None:
        mode = {"浅色": "light", "深色": "dark", "系统": "system"}.get(value, "system")
        if self._commit(lambda p: p.update(theme=mode)):
            ctk.set_appearance_mode(mode)
            self.theme_control.set(value)

    def _on_start(self) -> None:
        self._game_mode = False
        self._practice_restart = True
        super()._on_start()

    def _on_resume(self) -> None:
        self._game_mode = False
        self._practice_restart = False
        super()._on_resume()

    def _start_qids(self, qids, mode="自选") -> None:
        self._game_mode = False
        self._practice_restart = True
        super()._start_qids(qids, mode)

    def _start_stage(self, stage_id: str, restart: bool = False) -> None:
        level = game.level_for(self.g, stage_id)
        if level["world_id"] == "finance":
            act = next((a for a in finance.CONFIG["acts"] if level["chapter_no"] in a["chapters"]), None)
            if act and act["id"] not in finance.state(self.g)["story_seen"] and finance.act_open(self.g, act):
                self._open_finance_story(act["id"], after=lambda: self._start_stage(stage_id, restart))
                return
        self._flush_draft()
        attempt = self._commit(lambda p: game.start_attempt(p, stage_id, restart=restart))
        if not attempt:
            return
        self._game_mode = True
        self.current_qids = list(attempt["qids"])
        self.current_idx = min(attempt["index"], len(self.current_qids) - 1)
        level = game.level_for(self.g, stage_id)
        self.current_mode = "Boss 挑战" if level["kind"] == "boss" else "无尽远征" if level["kind"] == "expedition" else "冒险闯关"
        self._build_quiz()

    def _start_expedition(self) -> None:
        self._flush_draft()
        level = self._commit(lambda p: game.create_expedition(p, self.questions))
        if level:
            self._start_stage(level["id"])

    def _build_quiz(self) -> None:
        if not self._game_mode:
            if not self._commit(lambda p: skills.start_practice(p, self.current_qids, self.current_mode, self._practice_restart)):
                return
            self._practice_restart = False
            super()._build_quiz()
            # 自由刷题的长案例与答题卡也能滚动查看，保留原题目渲染和作答逻辑。
            self.body.destroy()
            self._practice_skills_enabled = True
            self._skill_controls = ctk.CTkFrame(self.page_area, fg_color="transparent")
            self._skill_controls.pack(fill="x", padx=44, pady=(8, 0))
            self.body = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
            self.body.pack(fill="both", expand=True, padx=36, pady=(10, 18))
            self._render_current()
            return
        self._hide_sidebar()
        self._clear()
        top = ctk.CTkFrame(self.page_area, fg_color="transparent")
        top.pack(fill="x", padx=22, pady=(12, 3))
        btn_ghost(top, text="← 保存并返回", width=115, height=31, font=_f(11), command=self._back_home).pack(side="left")
        self.lbl_meta = ctk.CTkLabel(top, text="", font=_f(11), text_color=C["text_sub"])
        self.lbl_meta.pack(side="left", padx=10)
        self.btn_fav = btn_soft(top, text="☆ 收藏", width=80, height=31, font=_f(11), command=self._toggle_favorite_current)
        self.btn_fav.pack(side="right")
        score_row = ctk.CTkFrame(self.page_area, fg_color="transparent")
        score_row.pack(fill="x", padx=25, pady=(0, 2))
        self.lbl_score = ctk.CTkLabel(score_row, text="", font=_f(12, "bold"), text_color=C["brand"])
        self.lbl_score.pack(side="left")
        level = game.level_for(self.g, self.g["active"]["stage_id"])
        self._game_scene = AdventureScene(self.page_area, self.sprites, self.g, biome=level["biome"], height=135,
                                           boss=level["kind"] == "boss")
        self._game_scene.pack(fill="x", padx=25, pady=(2, 5))
        self.progress_bar = ctk.CTkProgressBar(self.page_area, height=6, corner_radius=100)
        self.progress_bar.pack(fill="x", padx=25, pady=(3, 7))
        self._skill_controls = ctk.CTkFrame(self.page_area, fg_color="transparent")
        self._skill_controls.pack(fill="x", padx=25, pady=(0, 5))
        self.body = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        self._render_current()
        if store.is_subjective(self.qmap[self.current_qids[self.current_idx]]):
            self._game_scene.set_pose("think")

    def _answer_record(self, qid: str) -> dict | None:
        if self._game_mode:
            return self.g["active"]["answers"].get(qid)
        if self._practice_skills_enabled and self.progress.get("practice"):
            return self.progress["practice"]["answers"].get(qid)
        return super()._answer_record(qid)

    def _render_current(self) -> None:
        super()._render_current()
        if self.current_qids:
            q = self.qmap[self.current_qids[self.current_idx]]
            original_number = q.get("source_ref", {}).get("original_question_number")
            if original_number:
                self.lbl_meta.configure(text=f"{self._chapter_label(q)} · {q['type']} · 原题号 {original_number} [{self.current_mode}]")
        if self._game_mode and self.current_qids and self._game_scene:
            level = game.level_for(self.g, self.g["active"]["stage_id"])
            subjective = store.is_subjective(self.qmap[self.current_qids[self.current_idx]])
            self._game_scene.boss = level["kind"] == "boss" or (level["kind"] == "expedition" and subjective)
            self._game_scene.set_pose("think" if subjective and not self.answer_submitted else "idle")
            self._render_skill_controls()
            qid = self.current_qids[self.current_idx]
            if not subjective and not self.answer_submitted:
                for letter in self.g["active"].get("hints", {}).get(qid, []):
                    if letter in self.option_buttons:
                        self.option_buttons[letter].configure(state="disabled", text_color=C["text_sub"])
            for index, text in enumerate(self.g["active"].get("outlines", {}).get(qid, [])):
                card = self._card_frame(self.body)
                card.pack(fill="x", pady=5)
                ctk.CTkLabel(card, text=f"答题卡 {index + 1}  ·  {text}", font=_f(12), text_color=C["text"],
                             wraplength=920, justify="left", anchor="w").pack(fill="x", padx=15, pady=12)
            if hasattr(self.body, "_parent_canvas"):
                self.body._parent_canvas.yview_moveto(0)
        elif self._practice_skills_enabled and self.current_qids:
            self._render_skill_controls()
            a = self.progress["practice"]
            qid = self.current_qids[self.current_idx]
            if not store.is_subjective(self.qmap[qid]) and not self.answer_submitted:
                for letter in a.get("hints", {}).get(qid, []):
                    if letter in self.option_buttons:
                        self.option_buttons[letter].configure(state="disabled", text_color=C["text_sub"])
            cards = a.get("outlines", {}).get(qid, [])
            if cards and not self.answer_submitted and not self._finance_question():
                self.explain_box.configure(state="normal")
                self.explain_box.delete("1.0", "end")
                self.explain_box.insert("1.0", "妙笔生花 · 原参考答案分段卡\n\n" + "\n\n".join(f"答题卡 {i+1}\n{text}" for i, text in enumerate(cards)))
                self.explain_box.configure(state="disabled")

    def _render_skill_controls(self) -> None:
        if not (self._game_mode or self._practice_skills_enabled) or not self.current_qids:
            return
        for widget in self._skill_controls.winfo_children():
            widget.destroy()
        q = self.qmap[self.current_qids[self.current_idx]]
        subjective = store.is_subjective(q)
        skill_id = "outline" if subjective else "insight"
        s = skills.DEFINITIONS[skill_id]
        charges = skills.available(self.g, skill_id)
        a = self.g["active"] if self._game_mode else self.progress["practice"]
        saved = a.get("outlines" if subjective else "hints", {}).get(q["id"])
        button = btn_soft(self._skill_controls, text=f"{s['glyph']} {s['name']} · {charges} 次", height=30,
                          command=self._use_outline if subjective else self._use_hint)
        button.pack(side="left", padx=(0, 12))
        if self.answer_submitted or (not charges and not saved) or (subjective and not self.subj_ref_shown):
            button.configure(state="disabled")
        if not subjective and ((a.get("hint_used") and not saved) or len(q.get("options", {})) < 3):
            button.configure(state="disabled")
        hint = ("先写下答案，再看参考、整理答题卡" if subjective else "每场最多排除一个错误选项")
        if saved:
            hint = "本题答题卡已保存" if subjective else "已排除选项 " + "、".join(saved)
        ctk.CTkLabel(self._skill_controls, text=hint, font=_f(11), text_color=C["text_sub"]).pack(side="left")

    def _use_hint(self) -> None:
        if self.answer_submitted:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        excluded = self._commit(lambda p: skills.hint(p, q, self._practice_skills_enabled))
        if excluded:
            selection = self.current_selection - set(excluded)
            self._render_current()
            self.current_selection = selection
            self._refresh_option_styles(q)

    def _toggle_option(self, letter: str) -> None:
        if (self._game_mode or self._practice_skills_enabled) and self.current_qids:
            a = self.g["active"] if self._game_mode else self.progress["practice"]
            if letter in a.get("hints", {}).get(self.current_qids[self.current_idx], []):
                return
        super()._toggle_option(letter)

    def _use_outline(self) -> None:
        self._flush_draft()
        q = self.qmap[self.current_qids[self.current_idx]]
        def mutate(p):
            if self._practice_skills_enabled:
                if q.get("subquestions"):
                    attempt = p["practice"]
                    submission = attempt.get("structured_submissions", {}).get(q["id"])
                    snapshot = submission["draft"] if submission else finance.draft(attempt, q)
                    attempt["drafts"][q["id"]] = "\n".join(snapshot["process"].values())
                else:
                    p["practice"]["drafts"][q["id"]] = self.user_answer_box.get("1.0", "end").strip()
            return skills.outline(p, q, self._practice_skills_enabled)
        if self._commit(mutate):
            self._render_current()
            if hasattr(self.body, "_parent_canvas"):
                self.update_idletasks()
                self.body._parent_canvas.yview_moveto(1)

    def _toggle_favorite_current(self) -> None:
        if not self._game_mode:
            super()._toggle_favorite_current()
            return
        if not self.current_qids:
            return
        qid = self.current_qids[self.current_idx]
        result = self._commit(lambda p: {"favorite": store.toggle_favorite(p, qid)})
        if result:
            self.btn_fav.configure(text="★ 已收藏" if result["favorite"] else "☆ 收藏 (F)")

    def _render_score_only(self) -> None:
        if not self._game_mode:
            a = self.progress.get("practice") if self._practice_skills_enabled else None
            if a and a["qids"] == self.current_qids:
                answered = len(a["answers"])
                correct = sum(bool(rec["correct"]) for rec in a["answers"].values())
                self.lbl_score.configure(text=f"{self.current_idx+1}/{len(a['qids'])}  已答{answered}  正确率{correct/answered:.0%}" if answered else f"{self.current_idx+1}/{len(a['qids'])}  尚未作答")
                self.progress_bar.set((self.current_idx+1)/len(a["qids"]))
                return
            super()._render_score_only()
            return
        attempt = self.g["active"]
        total = len(attempt["qids"])
        answered = len(attempt["answers"])
        correct = sum(bool(rec["correct"]) for rec in attempt["answers"].values())
        required = math.ceil(total * game.CONFIG["pass_percent"] / 100)
        self.lbl_score.configure(text=f"第 {self.current_idx + 1}/{total} 题    已答 {answered}    答对 {correct}/{required} 即可通关")
        self.progress_bar.set(answered / total)

    def _update_action_buttons_objective(self) -> None:
        super()._update_action_buttons_objective()
        if self._game_mode:
            self.btn_redo.configure(state="disabled", text="本轮首次成绩")
            self.btn_next.configure(state="normal" if self.answer_submitted else "disabled",
                                    text="结算本关 ✓" if self.current_idx == len(self.current_qids) - 1 else "下一题 →")

    def _update_action_buttons_subjective(self) -> None:
        if self._finance_question():
            return
        super()._update_action_buttons_subjective()
        if self._game_mode:
            has_text = bool(self.user_answer_box.get("1.0", "end").strip())
            enabled = not self.answer_submitted and self.subj_ref_shown and has_text
            self.btn_mark_correct.configure(state="normal" if enabled else "disabled")
            self.btn_mark_wrong.configure(state="normal" if enabled else "disabled")
            self.btn_redo.configure(state="disabled", text="本轮首次成绩")
            self.btn_next.configure(state="normal" if self.answer_submitted else "disabled",
                                    text="结算本关 ✓" if self.current_idx == len(self.current_qids) - 1 else "下一题 →")

    def _render_subjective(self, q: dict) -> None:
        if q.get("subquestions"):
            self._render_finance_subjective(q)
            return
        super()._render_subjective(q)
        if not self._game_mode:
            a = self.progress.get("practice")
            if self._practice_skills_enabled and a and not self.answer_submitted:
                self.user_answer_box.insert("1.0", a["drafts"].get(q["id"], ""))
                if q["id"] in a["references"]:
                    App._show_reference_answer(self)
            self.user_answer_box.bind("<KeyRelease>", self._on_draft_key, add="+")
            return
        attempt = self.g["active"]
        if q["id"] not in attempt["answers"]:
            self.user_answer_box.delete("1.0", "end")
            self.user_answer_box.insert("1.0", attempt["drafts"].get(q["id"], ""))
            if q["id"] in attempt["references"]:
                App._show_reference_answer(self)
        self.user_answer_box.bind("<KeyRelease>", self._on_draft_key, add="+")
        self._update_action_buttons_subjective()

    def _on_draft_key(self, event=None) -> None:
        self._update_action_buttons_subjective()
        if self._draft_timer:
            self.after_cancel(self._draft_timer)
        self._draft_timer = self.after(700, self._flush_draft)

    def _flush_draft(self) -> None:
        self._draft_timer = None
        if self._finance_question():
            self._flush_finance_draft()
            return
        if not self.current_qids or self._pending_transaction:
            return
        attempt = self.g["active"] if self._game_mode else self.progress.get("practice") if self._practice_skills_enabled else None
        if not attempt:
            return
        box = getattr(self, "user_answer_box", None)
        if box is None or not box.winfo_exists():
            return
        qid = self.current_qids[self.current_idx]
        if not store.is_subjective(self.qmap[qid]) or qid in attempt["answers"]:
            return
        text = box.get("1.0", "end").strip()
        if text != attempt["drafts"].get(qid, ""):
            self._commit(lambda p: (p["game"]["active"] if self._game_mode else p["practice"])["drafts"].update({qid: text}))

    def _show_reference_answer(self) -> None:
        if self._finance_question():
            self._finance_submit()
            return
        if not self._game_mode:
            if self._practice_skills_enabled and self.current_qids:
                qid = self.current_qids[self.current_idx]
                text = self.user_answer_box.get("1.0", "end").strip()
                def practice_reference(p):
                    a = p["practice"]
                    a["drafts"][qid] = text
                    if qid not in a["references"]:
                        a["references"].append(qid)
                if not self._commit(practice_reference):
                    return
            super()._show_reference_answer()
            if self._practice_skills_enabled:
                self._render_skill_controls()
            return
        if not self.current_qids:
            return
        qid = self.current_qids[self.current_idx]
        text = self.user_answer_box.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("先试着作答", "先写下你的解题过程或结论，再查看参考答案并自评。")
            return
        def mark(p):
            attempt = p["game"]["active"]
            attempt["drafts"][qid] = text
            if qid not in attempt["references"]:
                attempt["references"].append(qid)
        if self._commit(mark):
            App._show_reference_answer(self)
            self._render_skill_controls()

    def _submit_answer(self) -> None:
        if not self._game_mode:
            if self._practice_skills_enabled and self.current_qids:
                q = self.qmap[self.current_qids[self.current_idx]]
                answer = self.current_judge if q["type"] == "判断题" else "".join(sorted(self.current_selection))
                if not answer or self.answer_submitted or store.is_subjective(q):
                    return
                correct = is_correct(q, answer)
                def submit(p):
                    a = p["practice"]
                    if q["id"] not in a["answers"]:
                        store.record_answer(p, q["id"], correct, answer)
                        a["answers"][q["id"]] = copy.deepcopy(p["answered"][q["id"]])
                if self._commit(submit):
                    self._render_current()
                return
            super()._submit_answer()
            if self._practice_skills_enabled:
                self._render_skill_controls()
            return
        if self.answer_submitted or not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if store.is_subjective(q):
            return
        answer = self.current_judge if q["type"] == "判断题" else "".join(sorted(self.current_selection))
        if not answer:
            return
        correct = is_correct(q, answer)
        if self._commit(lambda p: game.submit_answer(p, q, answer, correct)):
            self._render_current()
            level = game.level_for(self.g, self.g["active"]["stage_id"])
            self._game_scene.pulse(("attack" if level["kind"] == "boss" else "happy") if correct else "hurt")

    def _self_mark(self, correct: bool) -> None:
        if not self._game_mode:
            if self._practice_skills_enabled and self.current_qids:
                qid = self.current_qids[self.current_idx]
                answer = self.user_answer_box.get("1.0", "end").strip()
                if not answer or self.answer_submitted:
                    return
                def mark(p):
                    a = p["practice"]
                    if qid not in a["references"]:
                        raise ValueError("请先查看参考答案，再对照自评。")
                    if qid not in a["answers"]:
                        store.record_answer(p, qid, correct, answer)
                        a["answers"][qid] = copy.deepcopy(p["answered"][qid])
                if self._commit(mark):
                    self._render_current()
                return
            super()._self_mark(correct)
            if self._practice_skills_enabled:
                self._render_skill_controls()
            return
        if self.answer_submitted or not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        answer = self.user_answer_box.get("1.0", "end").strip()
        if self._commit(lambda p: game.submit_answer(p, q, answer, correct)):
            self._render_current()
            self._game_scene.pulse("attack" if correct else "hurt")

    def _next_q(self) -> None:
        self._flush_draft()
        if not self._game_mode:
            if self.current_qids and self.current_idx == len(self.current_qids)-1 and self._finance_finish_activity():
                return
            super()._next_q()
            return
        if not self.current_qids:
            return
        if self.current_qids[self.current_idx] not in self.g["active"]["answers"]:
            return
        if self.current_idx == len(self.current_qids) - 1:
            result = self._commit(lambda p: game.settle_attempt(p))
            if result:
                self._show_result(result)
            return
        index = self.current_idx + 1
        if self._commit(lambda p: p["game"]["active"].update(index=index)):
            self.current_idx = index
            self._render_current()
            self._game_scene.set_pose("think" if store.is_subjective(self.qmap[self.current_qids[index]]) else "idle")

    def _prev_q(self) -> None:
        self._flush_draft()
        if not self._game_mode:
            super()._prev_q()
            return
        self._flush_draft()
        if self.current_idx > 0 and self._commit(lambda p: p["game"]["active"].update(index=self.current_idx - 1)):
            self.current_idx -= 1
            self._render_current()

    def _redo_current(self) -> None:
        if not self._game_mode:
            if self._practice_skills_enabled and self.current_qids:
                qid = self.current_qids[self.current_idx]
                def clear(p):
                    store.clear_answer(p, qid)
                    p["practice"]["answers"].pop(qid, None)
                if self._commit(clear):
                    self._render_current()
                return
            super()._redo_current()

    def _goto_question(self) -> None:
        if not self._game_mode:
            super()._goto_question()

    def _back_home(self) -> None:
        self._flush_draft()
        if self._pending_transaction:
            return
        if not self._game_mode:
            super()._back_home()
            return
        self.current_qids = []
        self._game_mode = False
        self._show_page("home")

    def _show_result(self, result: dict) -> None:
        self.current_qids = []
        self._game_mode = False
        def build():
            g = self.g
            level = game.level_for(g, result["stage_id"])
            frame = self._scroll()
            passed = result["passed"]
            quality = result.get("quality", game.quality_for(result["correct"], result["total"]))
            high_quality = passed and result["stars"] >= 2
            heading = ("Boss 高质量击败！" if high_quality else "Boss 已击败！") if passed and level["kind"] == "boss" else "高质量通关！" if high_quality else "本关通关！" if passed else "差一点，再挑战一次"
            if result.get("assisted"):
                heading = "瞒天过海 · 技能通关！"
            self._heading(frame, heading,
                          level["chapter_title"] + " · " + level["name"])
            self._game_scene = AdventureScene(frame, self.sprites, g, biome=level["biome"], height=235,
                                               boss=level["kind"] == "boss", pose="celebrate" if passed else "hurt")
            self._game_scene.pack(fill="x", pady=(0, 12))
            card = self._card_frame(frame)
            card.pack(fill="x", pady=(0, 12))
            ctk.CTkLabel(card, text="★" * result["stars"] + "☆" * (3 - result["stars"]),
                         font=_f(32, "bold"), text_color="#DBAC38").pack(pady=(13, 4))
            ctk.CTkLabel(card, text=f"答对 {result['correct']}/{result['total']} · 正确率 {result['correct'] / result['total']:.0%}",
                         font=_f(18, "bold"), text_color=C["text"]).pack(pady=4)
            detail_quality = quality + (" · 三星全对" if result["stars"] == 3 else " · 下一关已解锁" if passed else f" · 至少 {game.CONFIG['pass_percent']}% 才能解锁")
            ctk.CTkLabel(card, text=detail_quality, font=_f(13, "bold"),
                         text_color=C["brand"] if high_quality else C["text_sub"]).pack(pady=3)
            ctk.CTkLabel(card, text=f"经验 +{result['xp']}     金币 +{result['coins']}", font=_f(14),
                         text_color=C["brand"]).pack(pady=(3, 13))
            if result.get("assisted"):
                ctk.CTkLabel(card, text="本轮消耗 1 次瞒天过海，真实成绩与错题已保留。", font=_f(11), text_color=C["text_sub"]).pack(pady=(0, 12))
            if result.get("level_after", 1) > result.get("level_before", 1):
                learned = "、".join(skills.DEFINITIONS[s]["name"] for s in result.get("new_skills", []))
                ctk.CTkLabel(frame, text=f"升级啦！Lv.{result['level_before']} → Lv.{result['level_after']}" + (f" · 学会 {learned}" if learned else ""),
                             font=_f(16, "bold"), text_color=C["brand"]).pack(pady=8)
            for reward in result.get("growth", []):
                surprise = self._card_frame(frame)
                surprise.pack(fill="x", pady=(0, 10))
                icon = self.sprites.item_icon(reward.get("id", ""), 72)
                if icon:
                    ctk.CTkLabel(surprise, text="", image=icon).pack(side="left", padx=12)
                ctk.CTkLabel(surprise, text="首通惊喜！" + reward["name"] + (f" · 重复兑换 {reward['coins']} 金币" if reward.get("duplicate") else ""),
                             font=_f(14, "bold"), text_color=C["brand"]).pack(padx=16, pady=16)
            loot = result.get("loot")
            loot_label = None
            if loot:
                chest = self._card_frame(frame)
                chest.pack(fill="x", pady=(0, 13))
                ctk.CTkLabel(chest, text="首次击败宝箱", font=_f(16, "bold"), text_color=C["brand"]).pack(pady=(13, 6))
                detail = loot["name"]
                if loot.get("rarity"):
                    detail = game.RARITY_NAMES[loot["rarity"]] + " · " + detail
                if loot.get("duplicate"):
                    detail += f" · 已拥有，兑换 {loot['coins']} 金币"
                loot_label = ctk.CTkLabel(chest, text="宝箱正在打开……", font=_f(18, "bold"), text_color=C["text"])
                loot_label.pack(pady=(0, 13))
            elif passed and level["kind"] == "boss":
                ctk.CTkLabel(frame, text="这个 Boss 的首次宝箱已结算。本次重玩只奖励新增星级。", font=_f(12), text_color=C["text_sub"]).pack(pady=8)
            buttons = ctk.CTkFrame(frame, fg_color="transparent")
            buttons.pack(fill="x", pady=(3, 14))
            next_button = None
            if passed:
                target = game.next_stage(g, result["stage_id"])
                if level["kind"] == "expedition" or (not target and game.campaign_complete(g)):
                    next_button = btn_primary(buttons, text="进入下一关 · 无尽远征 →", height=45, command=self._start_expedition)
                elif target:
                    next_button = btn_primary(buttons, text="高质量解锁 · 进入下一关 →" if high_quality else "进入下一关 →", height=45, command=lambda: self._start_stage(target))
                else:
                    next_button = btn_primary(buttons, text="本世界通关 · 返回选择另一科", height=45, command=lambda: self._show_page("home"))
                next_button.pack(fill="x", pady=4)
            else:
                a = g.get("active")
                status = skills.mercy_status(g, a, level) if a and a["id"] == result["attempt_id"] else {"eligible": False}
                if status["eligible"]:
                    mercy_button = btn_soft(buttons, text=f"☁ 瞒天过海 · 多错一题继续前进（{status['available']} 次）", height=42,
                                            command=self._use_mercy)
                    mercy_button.pack(fill="x", pady=4)
                    if not status["available"]:
                        mercy_button.configure(state="disabled", text="Lv.3 瞒天过海 · 到成长页补充技能后可用")
                    btn_ghost(buttons, text="查看成长与技能", height=30,
                              command=lambda: self._show_page("growth")).pack(fill="x", pady=3)
                btn_primary(buttons, text="再次挑战本关 →", height=45,
                    command=lambda: self._start_stage(result["stage_id"], restart=True)).pack(fill="x", pady=4)
            if result["wrong_qids"]:
                btn_soft(buttons, text=f"查看本轮 {len(result['wrong_qids'])} 道错题与解析", height=37,
                    command=lambda: self._review_result(result)).pack(fill="x", pady=4)
            btn_ghost(buttons, text="回到冒险地图", height=34, command=lambda: self._show_page("home")).pack(fill="x", pady=4)
            if passed and level["kind"] == "boss":
                next_button.configure(state="disabled", text="下一关即将点亮……")
                next_text = "进入下一关 →" if target else "开启无尽远征 →" if game.campaign_complete(g) else "本世界通关 · 返回选择另一科"
                if high_quality:
                    next_text = "高质量解锁 · " + next_text
                def reveal():
                    if loot_label:
                        loot_label.configure(text=detail)
                    next_button.configure(state="normal", text=next_text)
                self._game_scene.play_victory(reveal)
        self._show_page("home", build)

    def _use_mercy(self) -> None:
        result = self._commit(game.use_mercy)
        if result:
            self._show_result(result)

    def _review_result(self, result: dict) -> None:
        def build():
            frame = self._scroll()
            btn_ghost(frame, text="← 返回战绩", command=lambda: self._show_result(result)).pack(anchor="w", pady=(0, 12))
            self._heading(frame, "本轮错题回顾", "先读懂解析，再重新挑战。这里的回顾不会改变已结算成绩。")
            for index, qid in enumerate(result["wrong_qids"]):
                q = self.qmap[qid]
                card = self._card_frame(frame)
                card.pack(fill="x", pady=8)
                ctk.CTkLabel(card, text=f"{index + 1}. {q['stem']}", font=_f(13), text_color=C["text"],
                             wraplength=780, justify="left", anchor="w").pack(fill="x", padx=18, pady=(15, 8))
                text = f"参考答案：{q.get('answer', '')}\n\n{q.get('explanation', '')}"
                box = ctk.CTkTextbox(card, height=250, wrap="char", font=_f(12), fg_color=C["card"])
                box.pack(fill="x", padx=14, pady=(0, 14))
                box.insert("1.0", text)
                box.configure(state="disabled")
        self._show_page("home", build)

    def _build_bag(self) -> None:
        frame = self._scroll()
        g = self.g
        bonuses = game.equipment_bonuses(g)
        self._heading(frame, "小团的旅行商店", f"金币 {g['coins']} · 经验 +{bonuses['xp']}% · 金币 +{bonuses['coins']}% · 34 款兑换目标")
        welcome = self._card_frame(frame)
        welcome.pack(fill="x", pady=(0, 12))
        merchant = {**g, "skin": "orange_adventurer", "outfit": None, "equipment": {}}
        ctk.CTkLabel(welcome, text="", image=self.sprites.portrait(merchant, 86, "celebrate")).pack(side="left", padx=15, pady=10)
        welcome_text = ctk.CTkFrame(welcome, fg_color="transparent")
        welcome_text.pack(side="left", fill="x", expand=True, padx=8, pady=12)
        ctk.CTkLabel(welcome_text, text="把努力，换成下一件喜欢的宝贝。", font=_f(17, "bold"), text_color=C["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(welcome_text, text="普通 → 稀有 → 史诗 → 传说  ·  首通解锁上架，金币兑换收藏", font=_f(11), text_color=C["text_sub"], anchor="w").pack(fill="x", pady=5)
        self._goal_card(frame)
        tabs = ctk.CTkSegmentedButton(frame, values=["背包", "金币商店", "收藏图鉴"], font=_f(13),
                                    command=self._change_shop_tab, height=36)
        tabs.pack(fill="x", pady=(4, 12))
        tabs.set(self._shop_tab)
        filters = ctk.CTkFrame(frame, fg_color="transparent")
        filters.pack(fill="x", pady=(0, 12))
        for key, label in shop.CATEGORIES.items():
            button = (btn_primary if key == self._shop_filter else btn_soft)(filters, text=label, width=80, height=30,
                      font=_f(11), command=lambda k=key: self._change_shop_filter(k))
            button.pack(side="left", padx=(0, 6))
        if self._shop_detail:
            self._preview_card(frame, self._shop_detail)
        items = shop.view(g, self._shop_filter, self._shop_tab == "背包")
        if not items:
            ctk.CTkLabel(frame, text="这一格还空着。带着小圆去闯关，慢慢装满吧！", font=_f(13), text_color=C["text_sub"]).pack(pady=25)
        self._item_grid(frame, items)

    def _change_shop_tab(self, value):
        if value == "收藏图鉴":
            self._show_page("collection")
            return
        self._shop_tab = value
        self._shop_detail = None
        self._show_page("bag")

    def _change_shop_filter(self, key):
        self._shop_filter = key
        self._shop_detail = None
        self._show_page("bag")

    def _goal_card(self, parent):
        goal = shop.goal(self.g)
        if not goal:
            return
        card = self._card_frame(parent)
        card.pack(fill="x", pady=(0, 10))
        icon = self.sprites.item_icon(goal["id"], 60)
        if icon:
            ctk.CTkLabel(card, text="", image=icon).pack(side="left", padx=12, pady=8)
        text = ctk.CTkFrame(card, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        status = "已经收入背包！" if goal["owned"] else f"还差 {goal['remaining']} 金币" if goal["remaining"] else "金币攒够啦！"
        ctk.CTkLabel(text, text=f"我的心愿 · {goal['name']}   {status}", font=_f(12, "bold"), text_color=C["brand"], anchor="w").pack(fill="x")
        progress = ctk.CTkProgressBar(text, height=6)
        progress.pack(fill="x", pady=(7, 3))
        progress.set(min(1, self.g["coins"] / goal["price"]) if not goal["owned"] else 1)
        ctk.CTkLabel(text, text=goal["unlock_text"] or f"{goal['rarity_name']} · {goal['price']} 金币 · {goal['effect']}", font=_f(10), text_color=C["text_sub"], anchor="w").pack(fill="x")
        btn_soft(card, text="看看宝贝", width=92, height=30,
                 command=lambda: self._preview_item(goal["id"])).pack(side="right", padx=12)

    def _item_grid(self, parent, items):
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", pady=4)
        for column in (0, 1, 2):
            grid.grid_columnconfigure(column, weight=1, uniform="shop")
        for index, item in enumerate(items):
            self._item_card(grid, item, index)

    def _item_card(self, grid, item, index):
        card = self._card_frame(grid)
        card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=5, pady=6)
        color = game.CONFIG["rarities"].get(item["rarity"], {}).get("color", "#B98D28")
        icon = self.sprites.item_icon(item["id"], 100)
        if not item.get("skill_id") and (item.get("character") or item.get("outfit") or (item.get("slot") and not icon)):
            icon = self.sprites.portrait(shop.preview(self.g, item["id"]), 100)
        ctk.CTkLabel(card, text="" if icon else item.get("glyph", "✧"), image=icon,
                     font=_f(42, "bold"), text_color=color, height=110).pack(pady=(10, 0))
        ctk.CTkLabel(card, text=item["name"], font=_f(13, "bold"), text_color=C["text"], wraplength=225).pack(padx=12, pady=4)
        ctk.CTkLabel(card, text=("初始伙伴" if item.get("starter") else item["rarity_name"]) + (" · 使用中" if item["equipped"] else ""),
                     font=_f(11), text_color=color).pack(pady=3)
        ctk.CTkLabel(card, text=item["effect"], font=_f(11), text_color=C["text_sub"], wraplength=225,
                     justify="center", height=48).pack(fill="x", padx=12, pady=4)
        if item["unlock_text"]:
            ctk.CTkLabel(card, text=item["unlock_text"], font=_f(10), text_color=C["text_sub"]).pack(pady=2)
        if item["owned"]:
            label = "卸下" if item["equipped"] and not item.get("character") else "使用中" if item["equipped"] else "穿戴" if item["wearable"] else "已收藏"
            button = btn_soft(card, text=label, height=32, command=lambda: self._equip(item["id"]))
            if not item["wearable"] or label == "使用中":
                button.configure(state="disabled")
        else:
            label = f"补充 · {item['price']} 金币" if item.get("skill_id") else f"兑换 · {item['price']} 金币"
            button = btn_primary(card, text=label, height=32, font=_f(11), command=lambda: self._buy(item["id"]))
            if not item["can_buy"]:
                button.configure(state="disabled")
        button.pack(fill="x", padx=12, pady=5)
        btn_ghost(card, text="查看 / 试穿" if item["wearable"] else "查看故事", height=27, font=_f(10),
                  command=lambda: self._preview_item(item["id"])).pack(fill="x", padx=12, pady=(0, 10))

    def _preview_item(self, item_id):
        self._shop_detail = item_id
        self._show_page("bag")

    def _preview_card(self, parent, item_id):
        item = next((i for i in shop.view(self.g) + shop.view(self.g, owned_only=True) if i["id"] == item_id), None)
        if not item:
            return
        card = self._card_frame(parent)
        card.pack(fill="x", pady=(0, 14))
        icon = None
        if item["wearable"]:
            self._preview_game = shop.preview(self.g, item_id)
            icon = self.sprites.portrait(self._preview_game, 150)
        else:
            icon = self.sprites.item_icon(item_id, 120)
        ctk.CTkLabel(card, text="" if icon else item.get("glyph", "☆"), image=icon, font=_f(42), width=165).pack(side="left", padx=12, pady=12)
        text = ctk.CTkFrame(card, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=10, pady=13)
        ctk.CTkLabel(text, text=item["name"] + " · " + item["rarity_name"], font=_f(17, "bold"), text_color=C["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(text, text=item["story"], font=_f(12), text_color=C["text_sub"], anchor="w", wraplength=550, justify="left").pack(fill="x", pady=7)
        ctk.CTkLabel(text, text=item["effect"], font=_f(11), text_color=C["brand"], anchor="w", wraplength=550, justify="left").pack(fill="x", pady=3)
        actions = ctk.CTkFrame(text, fg_color="transparent")
        actions.pack(fill="x", pady=(7, 0))
        if not item.get("skill_id") and not item.get("starter"):
            btn_soft(actions, text="设为心愿", height=30, width=100, command=lambda: self._wishlist(item_id)).pack(side="left", padx=(0, 8))
        if item["owned"] and item["wearable"]:
            btn_primary(actions, text="穿戴 / 切换", height=30, width=120, command=lambda: self._equip(item_id)).pack(side="left", padx=(0, 8))
        elif not item["owned"]:
            button = btn_primary(actions, text=f"{item['price']} 金币兑换", height=30, width=130, command=lambda: self._buy(item_id))
            button.pack(side="left", padx=(0, 8))
            if not item["can_buy"]:
                button.configure(state="disabled")
        btn_ghost(actions, text="收起预览", width=85, height=30, command=self._close_preview).pack(side="right")

    def _close_preview(self):
        self._shop_detail = None
        self._show_page("bag")

    def _wishlist(self, item_id):
        if self._commit(lambda p: shop.set_wishlist(p, item_id)):
            self._show_page("bag")

    def _item_row(self, parent, item: dict) -> None:
        self._item_grid(parent, [shop.view_item(self.g, item)])

    def _buy(self, item_id: str) -> None:
        mutate = (lambda p: skills.refill(p, item_id.split(":", 1)[1])) if item_id.startswith("skill:") else (lambda p: game.buy_item(p, item_id))
        if self._commit(mutate):
            self._show_page("bag")

    def _equip(self, item_id: str) -> None:
        if self._commit(lambda p: game.equip_item(p, item_id)):
            self._show_page("bag")

    def _build_collection(self) -> None:
        frame = self._scroll()
        g = self.g
        chapter_count = sum(len(world["chapters"]) for world in g["campaign"]["worlds"])
        self._heading(frame, "冒险收藏图鉴", f"已拥有 {len(g['inventory'])}/{len(game.CATALOG)} 件物品 · {len(g['badges'])}/{chapter_count} 枚章节徽章")
        self._game_scene = AdventureScene(frame, self.sprites, g, biome="stars", height=185, pose="happy")
        self._game_scene.pack(fill="x", pady=(0, 15))
        self._heading(frame, "六地图旅行套装", "每个地图集齐主题装扮与纪念品，点亮一份完整的旅行回忆。")
        for biome in game.BIOMES:
            ids = ["outfit_" + biome["id"], "souvenir_" + biome["id"]]
            count = sum(i in g["inventory"] for i in ids)
            card = self._card_frame(frame)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text="", image=self.sprites.item_icon(ids[1], 62)).pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(card, text=f"{biome['name']} · {count}/2  {'旅行回忆已点亮！' if count == 2 else '慢慢收藏你的足迹'}", font=_f(12, "bold"),
                         text_color=C["brand"] if count == 2 else C["text"], anchor="w").pack(side="left", padx=12)
        self._heading(frame, "所有冒险物品")
        for item in game.CATALOG.values():
            owned = item["id"] in g["inventory"]
            card = self._card_frame(frame)
            card.pack(fill="x", pady=3)
            ctk.CTkLabel(card, text=("★  " if owned else "☆  ") + item["name"] + (" · 已收集" if owned else " · 等待发现"),
                         font=_f(12), text_color=C["brand"] if owned else C["text_sub"], anchor="w").pack(fill="x", padx=16, pady=10)
        self._heading(frame, "章节通关徽章")
        for world in g["campaign"]["worlds"]:
            for chapter in world["chapters"]:
                owned = chapter["id"] in g["badges"]
                ctk.CTkLabel(frame, text=("◆ " if owned else "◇ ") + chapter["title"], font=_f(11),
                             text_color=C["brand"] if owned else C["text_sub"], anchor="w").pack(fill="x", pady=3)

    def _build_growth(self) -> None:
        frame, g = self._scroll(), self.g
        level = skills.level(g)
        self._heading(frame, "小圆的成长之路", f"Lv.{level} · 累计经验 {g['xp']} · 每 500 经验升一级 · 金币 {g['coins']} · 魔法墨水 {g['skill_state']['ink']}")
        hero = self._card_frame(frame)
        hero.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hero, text="", image=self.sprites.portrait(g, 110, "celebrate")).pack(side="left", padx=16, pady=12)
        text = ctk.CTkFrame(hero, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=16, pady=15)
        next_skill = next((s for s in skills.view(g) if not s["unlocked"]), None)
        ctk.CTkLabel(text, text=f"再 {next_skill['xp_remaining']} 经验，学会「{next_skill['name']}」" if next_skill else "五种技能全部学会！", font=_f(16, "bold"), text_color=C["brand"], anchor="w").pack(fill="x")
        bar = ctk.CTkProgressBar(text, height=8)
        bar.pack(fill="x", pady=10)
        bar.set(g["xp"] % 500 / 500)
        ctk.CTkLabel(text, text=f"本级 {g['xp'] % 500}/500 经验 · 装备和技能帮助成长，真实作答决定成绩", font=_f(11), text_color=C["text_sub"], anchor="w").pack(fill="x")
        active = g.get("active")
        if active and active["settled"]:
            btn_soft(frame, text="返回本轮战绩 →", height=34, command=lambda: self._show_result(active["result"])).pack(fill="x", pady=(0, 12))
        self._heading(frame, "三格冒险装备", "经验护符、金币铃铛、魔法奇物可同时装备，加成在新挑战开始时固定。")
        slots = ctk.CTkFrame(frame, fg_color="transparent")
        slots.pack(fill="x", pady=(0, 14))
        for index, (slot, label) in enumerate((("xp", "经验护符"), ("coins", "金币铃铛"), ("wonder", "魔法奇物"))):
            slots.grid_columnconfigure(index, weight=1)
            card = self._card_frame(slots)
            card.grid(row=0, column=index, sticky="nsew", padx=5)
            item = game.CATALOG.get(g["equipment"].get(slot))
            icon = self.sprites.item_icon(item["id"], 70) if item else None
            ctk.CTkLabel(card, text="" if icon else "◇", image=icon, font=_f(32), height=75, text_color=C["brand"]).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label + "\n" + (item["name"] if item else "等待下一件宝贝"), font=_f(12), text_color=C["text"], wraplength=230).pack(padx=10, pady=(4, 12))
        self._heading(frame, "等级技能", "达到等级自动学会，初次获得 1 次机会；用金币卷轴或 1 瓶魔法墨水补充 1 次。")
        for s in skills.view(g):
            card = self._card_frame(frame)
            card.pack(fill="x", pady=5)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, padx=16, pady=13)
            ctk.CTkLabel(text, text=f"{s['glyph']}  Lv.{s['level']} {s['name']} · " + (f"可用 {s['charges']} 次" if s["unlocked"] else f"还需 {s['xp_remaining']} 经验"),
                         font=_f(15, "bold"), text_color=s["color"], anchor="w").pack(fill="x")
            ctk.CTkLabel(text, text=s["description"], font=_f(11), text_color=C["text_sub"], anchor="w", justify="left", wraplength=510).pack(fill="x", pady=5)
            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.pack(side="right", padx=13, pady=12)
            refill = btn_soft(buttons, text=f"{s['price']} 金币补充", height=28, width=122, font=_f(10), command=lambda sid=s["id"]: self._refill_skill(sid))
            refill.pack(pady=3)
            if not s["unlocked"] or g["coins"] < s["price"]:
                refill.configure(state="disabled")
            ink = btn_ghost(buttons, text="1 魔法墨水补充", height=26, width=122, font=_f(10), command=lambda sid=s["id"]: self._refill_skill(sid, True))
            ink.pack(pady=2)
            if not s["unlocked"] or not g["skill_state"]["ink"]:
                ink.configure(state="disabled")
            if s["type"] == "boost":
                queue = btn_primary(buttons, text="取消预约" if s["queued"] else "预约下次挑战", height=28, width=122, font=_f(10), command=lambda sid=s["id"]: self._queue_skill(sid))
                queue.pack(pady=3)
                if not s["queued"] and not s["charges"]:
                    queue.configure(state="disabled")
        self._heading(frame, "通关，解锁更多魔法奇物", "这里解锁的是商店上架资格。认真闯关赚金币，再把喜欢的奇物带回家。")
        milestones = []
        for m in game.growth_status(g):
            item = shop.view_item(g, game.CATALOG[m["item"]])
            item["effect"] = f"首通 {m['clears']} 关上架 · " + item["effect"]
            milestones.append(item)
        self._item_grid(frame, milestones)

    def _refill_skill(self, skill_id, with_ink=False):
        if self._commit(lambda p: skills.refill(p, skill_id, with_ink)):
            self._show_page("growth")

    def _queue_skill(self, skill_id):
        if self._commit(lambda p: skills.queue(p, skill_id)):
            self._show_page("growth")

    def _on_reset(self) -> None:
        if not messagebox.askyesno("重置全部进度", "将清空答题记录、错题、收藏、冒险地图、金币、经验与背包。\n此操作无法撤销。确定重置吗？"):
            return
        def reset(p):
            theme, scaling = p.get("theme", "system"), p.get("scaling", 1.0)
            p.clear()
            p.update(store.default_progress())
            p.update(theme=theme, scaling=scaling)
            game.ensure_game(p, self.questions)
        if self._commit(reset):
            self.current_qids = []
            self._game_mode = False
            self._show_page("home")

    def _on_close(self) -> None:
        self._flush_draft()
        if self._pending_transaction:
            if not messagebox.askyesno("仍有未保存内容", "有进度尚未写入磁盘。关闭后将丢失这次未保存变更。\n仍要关闭吗？"):
                return
        self.destroy()


AdventureApp._pages = {**App._pages, "home": "_build_home", "practice": "_build_practice", "town": "_build_finance_town",
                        "bag": "_build_bag", "collection": "_build_collection", "growth": "_build_growth"}


def main() -> None:
    mutex = None
    try:
        kernel = ctypes.windll.kernel32
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.GetLastError.restype = ctypes.c_ulong
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        data_dir = os.environ.get("XY_SHUATI_DATA_DIR")
        suffix = "-" + hashlib.sha256(os.path.abspath(data_dir).encode("utf-8")).hexdigest()[:12] if data_dir else ""
        mutex = kernel.CreateMutexW(None, False, "Local\\XiaoYuanAdventureOriginal-v02" + suffix)
        if kernel.GetLastError() == 183:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("小圆已经出发了", "小圆冒险世界已打开，请切换到现有窗口。")
            root.destroy()
            return
    except AttributeError:
        pass
    try:
        window = AdventureApp()
        icon = classic._icon_path()
        if icon:
            window.iconbitmap(icon)
        window.mainloop()
    except Exception as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("启动失败", "小圆暂时无法出发：\n" + str(error))
        root.destroy()
    finally:
        if mutex:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    main()
