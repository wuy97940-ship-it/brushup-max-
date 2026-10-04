"""小圆爱刷题MAX —— GUI 主程序（v3.3 侧边栏导航版）。

v3.3 UI 架构升级（业务逻辑与 v3.1/3.2 完全一致）：
- 参考 GitHub 成功 CustomTkinter 应用（CustomTkinter-UI-Studio / ctk-sidebar）
  与 Quizlet / Anki 等成熟刷题产品的界面模式重构：
  · 左侧品牌侧边栏导航（主页 / 章节训练 / 错题本 / 收藏夹 / 学习统计），
    替代原首页散落的按钮堆叠，二级页面不再各自画"返回"顶栏。
  · 主页改仪表盘式：统计卡 + 「快速开始」设置卡（2×2 筛选 + 全宽主 CTA）。
  · 答题页沉浸式：进入答题隐藏侧边栏，题干大卡片居中聚焦，进度条常驻。
- 修复樱粉主题从未生效的问题（theme JSON 的 dropdown_* 键名不合规 +
  缺 CTkFont/CTkTextbox 键 + 主题须在窗口创建前加载）。
- 全局统一小圆品牌视觉：淡蓝灰白底 + 品牌蓝主色 + 微软雅黑（v3.3.1 起弃用粉色）。
- 章节相关显示统一中文书名（原先直接暴露 book_id）。

历史版本要点（v2.0 / v3.1）：
- 四级筛选 book → chapter → type → mode，统计/错题本/收藏按 book_id 隔离。
- 客观题按钮作答 + 主观题自评两种渲染；快捷键输入框聚焦时自动让位。
- 真题模式仅出 exam_layer=official_exam 的题。
"""
from __future__ import annotations

import os
import random
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

import customtkinter as ctk

import store
from books import (
    ALL_BOOKS_VALUE,
    BOOKS,
    book_by_id,
    book_filter_values,
    book_id_to_name,
    book_name_to_id,
)
from store import (
    available_books,
    book_meta,
    book_progress,
    chapter_progress,
    clear_answer,
    default_progress,
    filter_by_book,
    is_subjective,
    load_progress,
    load_questions,
    overall_stats,
    questions_meta,
    record_answer,
    resource_path,
    save_progress,
    toggle_favorite,
)

APP_TITLE = "小圆冒险世界 · 原创公开版"
APP_VERSION = "v0.2.0-public.1"
ALL_BOOK = ALL_BOOKS_VALUE  # "全部书本"
ALL_CH = "全部章节"
ALL_TYPE = "全部题型"
ONLY_OBJ = "仅客观题"
ONLY_SUBJ = "仅主观题"
TYPES_OBJ = ["单选题", "多选题", "判断题", "不定项题"]
TYPES_SUBJ = ["计算分析题", "综合题", "简答题", "案例分析题"]
TYPE_FILTER_VALUES = [ALL_TYPE, ONLY_OBJ, ONLY_SUBJ] + TYPES_OBJ + TYPES_SUBJ
MODES = ["顺序刷题", "随机刷题", "错题重练", "未答题", "收藏题", "真题模式"]  # v3.1: 真题模式=仅official_exam层

# ----------------------------------------------------------------------
# 品牌视觉：调色板（浅色, 深色）+ 字体
# 参考：单一主色 + 中性辅色，绿/红仅用于对错反馈（成熟刷题应用的通用做法）
# v3.3.1：董事长批复弃用粉色，切换为蓝色系（皇家蓝 + 石板灰蓝中性色）
# ----------------------------------------------------------------------
FONT_FAMILY = "Microsoft YaHei UI"

SIDEBAR_W = 216  # 侧边栏宽度

C = {
    "brand":        ("#2563EB", "#7DB2FF"),   # 品牌蓝（标题/强调文字）
    "brand2":       ("#6366F1", "#93A8FF"),   # 辅助靛蓝
    "primary":      ("#3B82F6", "#2563EB"),   # 主按钮
    "primary_hover": ("#2563EB", "#3B82F6"),
    "soft":         ("#EAF2FF", "#1E3A5F"),   # 浅蓝底（选中导航/soft 按钮）
    "soft_hover":   ("#D8E8FF", "#25466F"),
    "soft_text":    ("#1D4ED8", "#A9C9FF"),
    "soft_border":  ("#A8C7FA", "#2F5680"),
    "card":         ("#FFFFFF", "#1E293B"),   # 卡片底
    "border":       ("#DCE6F2", "#2E3B4E"),   # 常规描边
    "text":         ("#334155", "#E8EEF6"),   # 正文
    "text_sub":     ("#94A3B8", "#8CA0B8"),   # 次要文字
    "green":        ("#2F9E6E", "#4ADE80"),   # 正确
    "green_bg":     ("#E6F6EF", "#16302A"),
    "green_border": ("#B5E3CF", "#2F5C46"),
    "red":          ("#E4574C", "#F87171"),   # 错误
    "red_bg":       ("#FDEDEC", "#3A2325"),
    "red_border":   ("#F6C6C2", "#6B363A"),
    "ghost_border": ("#E2E8F0", "#35435A"),   # 幽灵按钮
    "ghost_text":   ("#64748B", "#A8B8CC"),
    "ghost_hover":  ("#F1F5F9", "#26334A"),
    "sel_bg":       ("#DBEAFE", "#1E3A5F"),   # 选项选中态
    "sel_border":   ("#3B82F6", "#3B82F6"),
    # 侧边栏（比内容底色更"实"的一层）
    "side_bg":      ("#FFFFFF", "#141C28"),
    "side_hover":   ("#EFF6FF", "#1C2839"),
}


def apply_brand_theme(theme_mode: str = "system") -> None:
    """在任何窗口/控件创建之前调用：加载品牌主题 + 全局字体。"""
    ctk.set_appearance_mode(theme_mode)
    try:
        p = resource_path("assets/theme_xiaoyuan.json")
        ctk.set_default_color_theme(str(p) if p.exists() else "blue")
    except Exception:
        ctk.set_default_color_theme("blue")
    # 自定义主题缺 CTkFont / CTkTextbox 键（customtkinter 会直接 KeyError），补齐
    theme = ctk.ThemeManager.theme
    font_cfg = theme.get("CTkFont")
    if not isinstance(font_cfg, dict):
        theme["CTkFont"] = {"family": FONT_FAMILY, "size": 13, "weight": "normal"}
    elif "Windows" in font_cfg and isinstance(font_cfg.get("Windows"), dict):
        font_cfg["Windows"]["family"] = FONT_FAMILY
    else:
        font_cfg.setdefault("family", FONT_FAMILY)
    theme.setdefault("CTkTextbox", {
        "corner_radius": 10,
        "fg_color": C["card"],
        "border_color": C["border"],
        "border_width": 0,
        "text_color": C["text"],
        "scrollbar_button_color": C["ghost_border"],
        "scrollbar_button_hover_color": C["ghost_text"],
    })


def _f(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def btn_primary(parent, **kw) -> ctk.CTkButton:
    kw.setdefault("fg_color", C["primary"])
    kw.setdefault("hover_color", C["primary_hover"])
    kw.setdefault("text_color", ("#FFFFFF", "#FFFFFF"))
    return ctk.CTkButton(parent, **kw)


def btn_soft(parent, **kw) -> ctk.CTkButton:
    kw.setdefault("fg_color", C["soft"])
    kw.setdefault("hover_color", C["soft_hover"])
    kw.setdefault("text_color", C["soft_text"])
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", C["soft_border"])
    return ctk.CTkButton(parent, **kw)


def btn_ghost(parent, **kw) -> ctk.CTkButton:
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("hover_color", C["ghost_hover"])
    kw.setdefault("text_color", C["ghost_text"])
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", C["ghost_border"])
    return ctk.CTkButton(parent, **kw)


JUDGE_NORM = {"√": "√", "对": "√", "正确": "√", "T": "√", "TRUE": "√", "Y": "√", "1": "√",
              "×": "×", "X": "×", "错": "×", "错误": "×", "F": "×", "FALSE": "×", "N": "×", "2": "×"}


def norm_judge(value: str) -> str:
    """判断题答案归一：对/错/正确/错误/T/F/1/2 等写法统一为 √/×；未知值原样返回。"""
    v = (value or "").strip().upper()
    return JUDGE_NORM.get(v, (value or "").strip())


def is_correct(question: dict, user_answer: str) -> bool:
    correct = (question.get("answer") or "").strip()
    user = (user_answer or "").strip()
    if not correct:
        return False
    if question["type"] == "判断题":
        # 两侧都归一：库里答案可能是 对/错/正确/错误，按钮只有 √/×
        return norm_judge(user) == norm_judge(correct)
    return set(user.upper()) == set(correct.upper())


class App(ctk.CTk):
    def __init__(self) -> None:
        # 主题与字体必须在窗口创建前生效
        self.progress = load_progress()
        apply_brand_theme(self.progress.get("theme", "system"))
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x820")
        self.minsize(1020, 660)
        try:
            ctk.set_widget_scaling(float(self.progress.get("scaling", 1.0)))
        except Exception:
            pass

        try:
            self.questions: list[dict] = load_questions()
        except Exception as e:
            messagebox.showerror("题库加载失败", f"无法读取题库文件，程序即将退出。\n\n{e}")
            self.destroy()
            return

        if not self.questions:
            messagebox.showerror("题库为空", "题库中没有可用题目，请检查 data/questions.json。")
            self.destroy()
            return

        self.qmap: dict[str, dict] = {q["id"]: q for q in self.questions}
        self.meta = questions_meta(self.questions)
        self.books_avail = available_books(self.questions)  # 有题的 books
        self.books_meta = book_meta(self.questions)
        self.current_book_id: str | None = None  # None=全部书本

        self.current_qids: list[str] = []
        self.current_idx: int = 0
        self.current_mode: str = "顺序刷题"
        self.current_selection: set[str] = set()
        self.current_judge: str | None = None
        self.answer_submitted: bool = False
        self.subj_ref_shown: bool = False  # 当前主观题是否已显示参考答案

        # ── 整体骨架：左侧边栏 + 右侧内容区 ──
        self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_W, corner_radius=0,
                                    fg_color=C["side_bg"])
        self.sidebar.pack_propagate(False)
        self.sidebar.pack(side="left", fill="y")

        self.page_area = ctk.CTkFrame(self, fg_color="transparent")
        self.page_area.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._show_page("home")
        self._bind_global_keys()

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _clear(self) -> None:
        for w in self.page_area.winfo_children():
            w.destroy()

    def _show_page(self, name: str, builder=None) -> None:
        """切换页面并更新侧边栏选中态。"""
        if not self._sidebar_visible():
            self._show_sidebar()
        self._clear()
        self._set_active_nav(name)
        if builder is None:
            builder = getattr(self, self._pages[name])
        builder()

    def _sidebar_visible(self) -> bool:
        return self.sidebar.winfo_manager() != ""

    def _show_sidebar(self) -> None:
        self.sidebar.pack(side="left", fill="y", before=self.page_area)

    def _hide_sidebar(self) -> None:
        self.sidebar.pack_forget()

    def _chapter_label(self, q: dict) -> str:
        """章节统一显示名：中文书名 · 章节（避免直接暴露 book_id）。"""
        bid = q.get("book_id") or q.get("book") or ""
        bn = book_id_to_name(bid) if bid else ""
        ch = q.get("chapter") or ""
        if bn and ch:
            return f"{bn} · {ch}"
        return bn or ch

    def _type_match(self, q: dict, qtype: str) -> bool:
        if qtype == ALL_TYPE:
            return True
        if qtype == ONLY_OBJ:
            return q["type"] in store.OBJECTIVE_TYPES
        if qtype == ONLY_SUBJ:
            return q["type"] in store.SUBJECTIVE_TYPES
        return q["type"] == qtype

    def _chapters_for_book(self, book_id: str | None) -> list[str]:
        """返回 [全部章节] + 当前书本可用章节（按出现顺序）。"""
        chapters: list[str] = []
        seen: set[str] = set()
        for q in self.questions:
            if book_id and q.get("book_id") != book_id:
                continue
            ch = self._chapter_label(q)
            if ch and ch not in seen:
                seen.add(ch)
                chapters.append(ch)
        return chapters

    def _filter_questions(self, book_id: str | None, chapter: str, qtype: str) -> list[dict]:
        out = []
        for q in self.questions:
            if book_id and q.get("book_id") != book_id:
                continue
            if chapter != ALL_CH and self._chapter_label(q) != chapter:
                continue
            if not self._type_match(q, qtype):
                continue
            out.append(q)
        return out

    def _save(self) -> None:
        save_progress(self.progress)

    def _answer_record(self, qid: str) -> dict | None:
        """游戏挑战可以覆盖此入口，避免旧成绩直接成为本轮答案。"""
        return self.progress["answered"].get(qid)

    def _input_has_focus(self) -> bool:
        try:
            w = self.focus_get()
        except Exception:
            return False
        if w is None:
            return False
        cls = w.__class__.__name__
        return ("Text" in cls) or ("Entry" in cls)

    # ------------------------------------------------------------------
    # 侧边栏
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        s = self.sidebar

        # 品牌
        brand = ctk.CTkFrame(s, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(24, 20))
        ctk.CTkLabel(brand, text="🐱", font=_f(26)).pack(side="left")
        ctk.CTkLabel(brand, text=" 小圆爱刷题",
                     font=_f(19, "bold"), text_color=C["brand"]).pack(side="left", padx=(2, 0))
        ctk.CTkLabel(brand, text="MAX", font=_f(10, "bold"),
                     text_color=C["text_sub"]).pack(side="left", pady=(8, 0))

        # 导航
        self.nav_btns: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("home", "🏠  开始刷题", self._build_home),
            ("training", "🧩  章节训练", self._open_training),
            ("wrongbook", "🔁  错题本", self._open_wrongbook),
            ("favorites", "⭐  收藏夹", self._open_favorites),
            ("stats", "📊  学习统计", self._open_chapter_stats),
        ]
        for key, label, builder in nav_items:
            btn = ctk.CTkButton(
                s, text=label, anchor="w", height=42, corner_radius=12,
                font=_f(13), fg_color="transparent",
                hover_color=C["side_hover"], text_color=C["text"],
                command=lambda k=key, b=builder: self._show_page(k, b),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_btns[key] = btn

        # 底部：主题切换 + 版本 + 清空进度
        bottom = ctk.CTkFrame(s, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=16, pady=16)

        self.appearance = ctk.CTkSegmentedButton(
            bottom, values=["浅色", "深色", "系统"],
            font=_f(11), height=28,
            command=self._on_theme_change,
        )
        self.appearance.set({"light": "浅色", "dark": "深色", "system": "系统"}.get(
            self.progress.get("theme", "system"), "系统"))
        self.appearance.pack(fill="x", pady=(0, 10))

        btn_ghost(
            bottom, text="清空进度", font=_f(11), height=28, corner_radius=9,
            command=self._on_reset,
        ).pack(fill="x", pady=(0, 8))

        _real_n = sum(1 for q in self.questions if q.get("exam_layer") == "official_exam")
        ctk.CTkLabel(bottom, text=f"{APP_VERSION} · {len(self.questions)} 题 · 真题 {_real_n}",
                     font=_f(10), text_color=C["text_sub"]).pack(anchor="w")

    def _set_active_nav(self, name: str) -> None:
        for key, btn in self.nav_btns.items():
            if key == name:
                btn.configure(fg_color=C["soft"], text_color=C["soft_text"],
                              font=_f(13, "bold"))
            else:
                btn.configure(fg_color="transparent", text_color=C["text"],
                              font=_f(13))

    # ------------------------------------------------------------------
    # 主页（仪表盘）
    # ------------------------------------------------------------------
    def _build_home(self) -> None:
        # 记忆上次的 book_id
        last_book_name = self.progress["last"].get("filter_book", ALL_BOOK)
        last_book_id = book_name_to_id(last_book_name) if last_book_name != ALL_BOOK else None
        if last_book_id and not book_by_id(last_book_id):
            last_book_id = None
        self.current_book_id = last_book_id

        body = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(24, 0))

        # 欢迎语
        ctk.CTkLabel(body, text="今天也一起加油呀 🐾",
                     font=_f(22, "bold"), text_color=C["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(body, text="选好范围，随时开始——真题优先，错题及时清。",
                     font=_f(12), text_color=C["text_sub"], anchor="w").pack(fill="x", pady=(2, 16))

        # ── 统计：四张小卡 ──
        stats = overall_stats(self.progress, self.questions, self.current_book_id)
        _real_total = sum(1 for q in self.questions if q.get("exam_layer") == "official_exam")
        cards_row = ctk.CTkFrame(body, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 14))
        cards_row.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")

        def stat_card(col: int, icon: str, value: str, label: str, color):
            card = ctk.CTkFrame(cards_row, corner_radius=16, fg_color=C["card"],
                                border_width=1, border_color=C["border"])
            card.grid(row=0, column=col, sticky="nsew", padx=(0, 12 if col < 3 else 0))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=20, pady=16)
            ctk.CTkLabel(inner, text=f"{icon}  {label}", font=_f(12),
                         text_color=C["text_sub"], anchor="w").pack(fill="x")
            ctk.CTkLabel(inner, text=value, font=_f(26, "bold"),
                         text_color=color, anchor="w").pack(fill="x", pady=(4, 0))

        stat_card(0, "📚", f"{stats['total']}", f"题库 · 已答 {stats['answered']}", C["text"])
        stat_card(1, "✅", f"{stats['rate']:.1f}%", "正确率", C["brand"])
        stat_card(2, "🔁", f"{stats['wrong_count']} / {stats['fav_count']}", "错题 / 收藏", C["text"])
        stat_card(3, "🏛", f"{_real_total}", f"真题 · 全书 {len(self.questions)}", C["brand2"])

        # ── 快速开始卡 ──
        setup = ctk.CTkFrame(body, corner_radius=16, fg_color=C["card"],
                             border_width=1, border_color=C["border"])
        setup.pack(fill="x", pady=(0, 12))
        su = ctk.CTkFrame(setup, fg_color="transparent")
        su.pack(fill="x", padx=24, pady=(16, 20))
        su.grid_columnconfigure((0, 1), weight=1, uniform="sel")

        head = ctk.CTkFrame(su, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(head, text="🎯 快速开始", font=_f(15, "bold"),
                     text_color=C["text"], anchor="w").pack(side="left")

        last_qids = self.progress["last"].get("qids") or []
        resume_idx = self.progress["last"].get("index", 0)
        if last_qids:
            resume_text = f"继续上次 ({min(resume_idx, len(last_qids) - 1) + 1}/{len(last_qids)})"
            resume_state = "normal"
        else:
            resume_text = "继续上次"
            resume_state = "disabled"
        btn_resume = btn_soft(
            head, text=resume_text, font=_f(12, "bold"),
            height=32, corner_radius=11, command=self._on_resume,
        )
        btn_resume.pack(side="right")
        btn_resume.configure(state=resume_state)

        def sel_cell(row: int, col: int, label: str, var: ctk.StringVar,
                     values: list[str], command=None) -> ctk.CTkOptionMenu:
            cell = ctk.CTkFrame(su, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="ew", padx=(0, 14 if col == 0 else 0), pady=4)
            ctk.CTkLabel(cell, text=label, font=_f(11),
                         text_color=C["text_sub"], anchor="w").pack(fill="x", pady=(0, 3))
            menu = ctk.CTkOptionMenu(
                cell, values=values, variable=var, height=38,
                font=_f(12), dynamic_resizing=False, command=command,
            )
            menu.pack(fill="x")
            return menu

        book_values = [ALL_BOOK] + [b["name"] for b in self.books_avail]
        self.book_var = ctk.StringVar(value=last_book_name if last_book_name in book_values else ALL_BOOK)
        sel_cell(1, 0, "书本", self.book_var, book_values, command=self._on_book_change)

        chapters = [ALL_CH] + self._chapters_for_book(self.current_book_id)
        last_chapter = self.progress["last"].get("filter_chapter", ALL_CH)
        self.chapter_var = ctk.StringVar(value=last_chapter if last_chapter in chapters else ALL_CH)
        self._chapter_menu = sel_cell(1, 1, "章节", self.chapter_var, chapters)

        last_type = self.progress["last"].get("filter_type", ALL_TYPE)
        self.type_var = ctk.StringVar(value=last_type if last_type in TYPE_FILTER_VALUES else ALL_TYPE)
        sel_cell(2, 0, "题型", self.type_var, TYPE_FILTER_VALUES)

        last_mode = self.progress["last"].get("mode")
        self.mode_var = ctk.StringVar(value=last_mode if last_mode in MODES else MODES[0])
        sel_cell(2, 1, "模式", self.mode_var, MODES)

        btn_primary(
            su, text="开始刷题  →", font=_f(15, "bold"),
            height=48, corner_radius=13,
            command=self._on_start,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 0))

        # 快捷键提示（单行）
        ctk.CTkLabel(
            body,
            text="快捷键　1-4 选择 · Enter 提交/下一题 · ←→ 切题 · F 收藏 · R 重做 · G 跳转 · Esc 返回",
            font=_f(11), text_color=C["text_sub"],
        ).pack(fill="x", pady=(2, 16))

    def _on_book_change(self, value: str) -> None:
        """书本切换：刷新章节下拉、统计、记忆。"""
        new_id = book_name_to_id(value) if value != ALL_BOOK else None
        self.current_book_id = new_id
        self.progress["last"]["filter_book"] = value
        # 章节下拉重建
        chapters = [ALL_CH] + self._chapters_for_book(self.current_book_id)
        if self._chapter_menu is not None:
            self._chapter_menu.configure(values=chapters)
        if self.chapter_var.get() not in chapters:
            self.chapter_var.set(ALL_CH)
        self._save()
        # 重建首页（刷新统计卡片）—— 简单做法：整页重建
        self._show_page("home")

    # ------------------------------------------------------------------
    # 章节训练面板
    # ------------------------------------------------------------------
    def _open_training(self) -> None:
        body = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(24, 0))

        ctk.CTkLabel(body, text="🧩 章节训练",
                     font=_f(22, "bold"), text_color=C["text"],
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(body, text="自选章节与题量，集中突破薄弱环节。",
                     font=_f(12), text_color=C["text_sub"],
                     anchor="w").pack(fill="x", pady=(2, 16))

        # 书本章节数据
        book_id = self.current_book_id
        chapters_map: dict[str, list[dict]] = {}
        for q in self.questions:
            if book_id and q.get("book_id") != book_id:
                continue
            ch_name = self._chapter_label(q)
            if not ch_name:
                continue
            chapters_map.setdefault(ch_name, []).append(q)

        if not chapters_map:
            ctk.CTkLabel(body, text="当前书本下没有可训练的章节。",
                         font=_f(14)).pack(pady=40)
            return

        # 书本章节列表
        sorted_chapters = sorted(chapters_map.keys())
        self.train_count_var = ctk.IntVar(value=10)

        # 题量选择
        count_card = ctk.CTkFrame(body, corner_radius=16, fg_color=C["card"],
                                  border_width=1, border_color=C["border"])
        count_card.pack(fill="x", pady=(0, 12))
        cc_inner = ctk.CTkFrame(count_card, fg_color="transparent")
        cc_inner.pack(fill="x", padx=24, pady=14)

        ctk.CTkLabel(cc_inner, text="每次训练题量",
                     font=_f(13, "bold"),
                     text_color=C["text"]).pack(side="left", padx=(0, 16))
        for n in [10, 15, 20]:
            ctk.CTkRadioButton(
                cc_inner, text=f"{n} 道", variable=self.train_count_var, value=n,
                font=_f(13),
                fg_color=C["brand"],
                hover_color=C["primary_hover"],
            ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(body, text=f"共 {len(sorted_chapters)} 章",
                     font=_f(12), text_color=C["text_sub"]).pack(anchor="w", pady=(4, 8))

        for ch_name in sorted_chapters:
            ch_qs = chapters_map[ch_name]
            n = len(ch_qs)
            row = ctk.CTkFrame(body, corner_radius=14, fg_color=C["card"],
                               border_width=1, border_color=C["border"])
            row.pack(fill="x", pady=3)

            row_inner = ctk.CTkFrame(row, fg_color="transparent")
            row_inner.pack(fill="x", padx=20, pady=11)

            ctk.CTkLabel(row_inner, text=ch_name,
                         font=_f(13, "bold"),
                         anchor="w", justify="left").pack(side="left")
            ctk.CTkLabel(row_inner, text=f"{n} 题",
                         font=_f(12),
                         text_color=C["text_sub"]).pack(side="left", padx=10)

            btn_soft(
                row_inner, text="开始训练", width=100, height=32, corner_radius=10,
                font=_f(12, "bold"),
                command=lambda ch=ch_name, qs=ch_qs: self._start_training(ch, qs),
            ).pack(side="right")

    def _start_training(self, chapter_name: str, pool: list[dict]) -> None:
        n = self.train_count_var.get()
        if len(pool) <= n:
            selected = list(pool)
        else:
            selected = random.sample(pool, n)
        qids = [q["id"] for q in selected]
        # 按编号排序让体验更好
        qids_sorted = sorted(qids, key=lambda qid: self.qmap[qid].get("num", 0))
        self._start_qids(qids_sorted, mode=f"训练 · {chapter_name} ({len(qids_sorted)}题)")

    def _on_theme_change(self, value: str) -> None:
        mapping = {"浅色": "light", "深色": "dark", "系统": "system"}
        m = mapping.get(value, "system")
        ctk.set_appearance_mode(m)
        self.progress["theme"] = m
        self._save()

    def _on_reset(self) -> None:
        if not messagebox.askyesno("确认", "清空所有答题记录、错题本、收藏与进度？此操作不可撤销。"):
            return
        theme = self.progress.get("theme", "system")
        scaling = self.progress.get("scaling", 1.0)
        self.progress = default_progress()
        self.progress["theme"] = theme
        self.progress["scaling"] = scaling
        self._save()
        self._show_page("home")

    # ------------------------------------------------------------------
    # 开始 / 恢复
    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        book_name = self.book_var.get()
        book_id = book_name_to_id(book_name) if book_name != ALL_BOOK else None
        chapter = self.chapter_var.get()
        qtype = self.type_var.get()
        mode = self.mode_var.get()

        pool = self._filter_questions(book_id, chapter, qtype)

        if mode == "错题重练":
            wrong_set = set(self.progress.get("wrong_book", []))
            pool = [q for q in pool if q["id"] in wrong_set]
            if not pool:
                messagebox.showinfo("提示", "当前筛选条件下没有错题。")
                return
        elif mode == "未答题":
            ans = self.progress.get("answered", {})
            pool = [q for q in pool if q["id"] not in ans]
            if not pool:
                messagebox.showinfo("提示", "当前筛选条件下没有未答题。")
                return
        elif mode == "收藏题":
            fav_set = set(self.progress.get("favorites", []))
            pool = [q for q in pool if q["id"] in fav_set]
            if not pool:
                messagebox.showinfo("提示", "当前筛选条件下没有收藏题。")
                return
        elif mode == "真题模式":
            # v3.1: 仅出带真题年份标记的题(exam_layer=official_exam)，真题优先原则
            pool = [q for q in pool if q.get("exam_layer") == "official_exam"]
            if not pool:
                messagebox.showinfo("提示", "当前筛选条件下没有真题。")
                return

        if not pool:
            messagebox.showinfo("提示", "当前筛选条件下没有题目。")
            return

        qids = [q["id"] for q in pool]
        if mode == "随机刷题":
            random.shuffle(qids)

        self.current_qids = qids
        self.current_idx = 0
        self.current_mode = mode
        self.progress["last"] = {
            "mode": mode,
            "filter_book": book_name,
            "filter_chapter": chapter,
            "filter_type": qtype,
            "index": 0,
            "qids": qids,
        }
        self._save()
        self._build_quiz()

    def _on_resume(self) -> None:
        last = self.progress.get("last", {})
        qids = [q for q in (last.get("qids") or []) if q in self.qmap]
        if not qids:
            messagebox.showinfo("提示", "没有可恢复的上次进度。")
            return
        self.current_qids = qids
        self.current_idx = max(0, min(last.get("index", 0), len(qids) - 1))
        self.current_mode = last.get("mode", "顺序刷题")
        self._build_quiz()

    def _start_qids(self, qids: list[str], mode: str = "自选") -> None:
        qids = [q for q in qids if q in self.qmap]
        if not qids:
            messagebox.showinfo("提示", "没有可练习的题目。")
            return
        self.current_qids = qids
        self.current_idx = 0
        self.current_mode = mode
        self.progress["last"] = {
            "mode": mode,
            "filter_book": ALL_BOOK,
            "filter_chapter": ALL_CH,
            "filter_type": ALL_TYPE,
            "index": 0,
            "qids": qids,
        }
        self._save()
        self._build_quiz()

    # ------------------------------------------------------------------
    # 答题界面（沉浸式：隐藏侧边栏）
    # ------------------------------------------------------------------
    def _build_quiz(self) -> None:
        # 沉浸式：隐藏侧边栏（参考 Quizlet 的专注答题模式）
        self._hide_sidebar()
        self._clear()

        top = ctk.CTkFrame(self.page_area, height=52, corner_radius=0, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(14, 0))
        btn_ghost(
            top, text="← 返回", width=90, height=34, corner_radius=11,
            font=_f(12),
            command=self._back_home,
        ).pack(side="left")

        self.lbl_meta = ctk.CTkLabel(top, text="", font=_f(12),
                                     text_color=C["text_sub"])
        self.lbl_meta.pack(side="left", padx=12)

        self.lbl_score = ctk.CTkLabel(
            top, text="", font=_f(13, "bold"),
            text_color=C["brand"],
        )
        self.lbl_score.pack(side="right", padx=6)

        self.btn_fav = btn_soft(
            top, text="☆ 收藏 (F)", width=96, height=34, corner_radius=11,
            font=_f(12),
            command=self._toggle_favorite_current,
        )
        self.btn_fav.pack(side="right", padx=4)

        btn_ghost(
            top, text="跳转 (G)", width=80, height=34, corner_radius=11,
            font=_f(12),
            command=self._goto_question,
        ).pack(side="right", padx=4)

        self.progress_bar = ctk.CTkProgressBar(self.page_area, height=6, corner_radius=1000)
        self.progress_bar.pack(fill="x", padx=28, pady=(10, 0))
        self.progress_bar.set(0)

        self.body = ctk.CTkFrame(self.page_area, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=44, pady=(12, 18))

        self._render_current()

    def _render_current(self) -> None:
        if not self.current_qids:
            self._back_home()
            return
        self.current_idx = max(0, min(self.current_idx, len(self.current_qids) - 1))
        q = self.qmap[self.current_qids[self.current_idx]]

        self.lbl_meta.configure(
            text=f"{self._chapter_label(q)} · {q['type']} · 第 {q['num'] + 1} 题  [{self.current_mode}]"
        )
        self._render_score_only()

        is_fav = q["id"] in self.progress.get("favorites", [])
        self.btn_fav.configure(text=("★ 已收藏" if is_fav else "☆ 收藏 (F)"))

        # 重建 body
        for w in self.body.winfo_children():
            w.destroy()

        if is_subjective(q):
            self._render_subjective(q)
        else:
            self._render_objective(q)

    # ------------------------------------------------------------------
    # 卡片容器（题干 / 解析共用）
    # ------------------------------------------------------------------
    def _card(self, parent, accent: bool = False) -> ctk.CTkFrame:
        """白色圆角卡片；accent=True 时左侧加品牌竖条。"""
        card = ctk.CTkFrame(parent, corner_radius=16, fg_color=C["card"],
                            border_width=1, border_color=C["border"])
        if accent:
            bar = ctk.CTkFrame(card, width=4, corner_radius=2, fg_color=C["brand"])
            bar.pack(side="left", fill="y", padx=(12, 0), pady=14)
        return card

    @staticmethod
    def _stem_height(text: str, font_size: int = 15) -> int:
        """按内容估算题干框高度（自适应短题干，超长封顶滚动）。"""
        import math
        lines = 0
        for raw in (text or "").split("\n"):
            width_units = sum(1.0 if ord(ch) > 127 else 0.55 for ch in raw)
            lines += max(1, math.ceil(width_units / 60))
        lines = max(lines, 1)
        h = lines * (font_size + 8) + 18
        return max(64, min(h, 420))

    # ------------------------------------------------------------------
    # 客观题分支
    # ------------------------------------------------------------------
    def _render_objective(self, q: dict) -> None:
        self.answer_submitted = False
        self.current_selection = set()
        self.current_judge = None

        stem_card = self._card(self.body, accent=True)
        stem_card.pack(fill="x", pady=(0, 10))
        self.stem_box = ctk.CTkTextbox(
            stem_card, height=self._stem_height(q["stem"]),
            font=_f(15),
            wrap="char", activate_scrollbars=True,
            fg_color=C["card"], border_width=0,
        )
        self.stem_box.pack(fill="x", padx=(8, 14), pady=(2, 8))
        self.stem_box.insert("1.0", q["stem"])
        self.stem_box.configure(state="disabled")

        self.options_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        self.options_frame.pack(fill="x", pady=(0, 10))

        action_row = ctk.CTkFrame(self.body, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 6))
        self.btn_submit = btn_primary(
            action_row, text="提交答案 (Enter)",
            font=_f(14, "bold"),
            height=42, width=170, corner_radius=13,
            command=self._submit_answer,
        )
        self.btn_submit.pack(side="left", padx=(0, 8))
        self.btn_redo = btn_ghost(
            action_row, text="重做本题 (R)",
            font=_f(13),
            height=42, width=126, corner_radius=13,
            command=self._redo_current,
        )
        self.btn_redo.pack(side="left", padx=(0, 8))

        self.btn_next = btn_ghost(
            action_row, text="下一题 →",
            font=_f(13),
            height=42, width=116, corner_radius=13,
            command=self._next_q,
        )
        self.btn_next.pack(side="right", padx=(4, 0))
        self.btn_prev = btn_ghost(
            action_row, text="← 上一题",
            font=_f(13),
            height=42, width=116, corner_radius=13,
            command=self._prev_q,
        )
        self.btn_prev.pack(side="right")

        # 解析卡
        explain_card = self._card(self.body)
        explain_card.pack(fill="both", expand=True, pady=(8, 0))
        ctk.CTkLabel(explain_card, text="💡 解析", font=_f(12, "bold"),
                     text_color=C["brand"], anchor="w").pack(fill="x", padx=20, pady=(12, 0))
        self.explain_box = ctk.CTkTextbox(
            explain_card, height=200,
            font=_f(13),
            wrap="char",
            fg_color=C["card"], border_width=0,
        )
        self.explain_box.pack(fill="both", expand=True, padx=20, pady=(4, 14))

        # 选项按钮
        self.option_buttons: dict[str, ctk.CTkButton] = {}
        if q["type"] == "判断题":
            for label, val in [("√  正确  (按 1)", "√"), ("×  错误  (按 2)", "×")]:
                btn = ctk.CTkButton(
                    self.options_frame, text=label,
                    font=_f(15),
                    height=50, corner_radius=13, anchor="w",
                    fg_color=C["card"], hover_color=C["sel_bg"],
                    text_color=C["text"], border_width=1, border_color=C["border"],
                    command=lambda v=val: self._toggle_judge(v),
                )
                btn.pack(fill="x", pady=3)
                self.option_buttons[val] = btn
        else:
            options = q.get("options") or {}
            # v3.5: 按实际选项键渲染（兼容非标准题的E/F/G选项），缺键时退回ABCD
            letters = sorted(k for k in options if k) or ["A", "B", "C", "D"]
            for letter in letters:
                text = options.get(letter, "（缺失）")
                btn = ctk.CTkButton(
                    self.options_frame,
                    text=f"  {letter}.  {text}",
                    font=_f(14),
                    height=50, corner_radius=13, anchor="w",
                    fg_color=C["card"], hover_color=C["sel_bg"],
                    text_color=C["text"], border_width=1, border_color=C["border"],
                    command=lambda l=letter: self._toggle_option(l),
                )
                btn.pack(fill="x", pady=3)
                self.option_buttons[letter] = btn

        # 解析区初始化 + 状态恢复
        self._option_wrap_width = None
        self.options_frame.bind("<Configure>", self._wrap_option_text, add="+")
        self.explain_box.configure(state="normal")
        self.explain_box.delete("1.0", "end")
        rec = self._answer_record(q["id"])
        if rec:
            self.answer_submitted = True
            user_ans = rec.get("user_answer", "")
            if q["type"] == "判断题":
                self.current_judge = user_ans
            else:
                self.current_selection = set(user_ans.upper())
            self._highlight_options(q, user_ans)
            self._render_explanation_objective(q, user_ans, rec.get("correct", False))
        else:
            self.explain_box.insert("1.0", "提交答案后这里会显示正确答案与解析。")
            self.explain_box.configure(state="disabled")

        self._update_action_buttons_objective()

    def _wrap_option_text(self, event) -> None:
        """按实际窗口宽度换行，长选项也能完整阅读。"""
        import math
        import tkinter.font as tkfont
        width = max(140, event.width - 52)
        if width == self._option_wrap_width:
            return
        self._option_wrap_width = width
        for button in self.option_buttons.values():
            label = button._text_label
            if label is None:
                continue
            label.configure(wraplength=width, justify="left")
            font = tkfont.Font(font=label.cget("font"))
            lines = sum(max(1, math.ceil(font.measure(line) / width)) for line in button.cget("text").split("\n"))
            height = max(50, (lines * font.metrics("linespace") + 25) / self._get_widget_scaling())
            button.configure(height=height)

    def _update_action_buttons_objective(self) -> None:
        if self.current_idx == 0:
            self.btn_prev.configure(state="disabled")
        else:
            self.btn_prev.configure(state="normal")
        if self.current_idx >= len(self.current_qids) - 1:
            self.btn_next.configure(text="完成 ✓")
        else:
            self.btn_next.configure(text="下一题 →")
        if self.answer_submitted:
            self.btn_submit.configure(state="disabled", text="已提交")
            self.btn_redo.configure(state="normal")
        else:
            self.btn_submit.configure(state="normal", text="提交答案 (Enter)")
            self.btn_redo.configure(state="disabled")

    def _toggle_option(self, letter: str) -> None:
        if self.answer_submitted:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if q["type"] == "单选题":
            self.current_selection = {letter}
            self._refresh_option_styles(q)
            self._submit_answer()
        else:
            if letter in self.current_selection:
                self.current_selection.remove(letter)
            else:
                self.current_selection.add(letter)
            self._refresh_option_styles(q)

    def _toggle_judge(self, val: str) -> None:
        if self.answer_submitted:
            return
        self.current_judge = val
        q = self.qmap[self.current_qids[self.current_idx]]
        self._refresh_option_styles(q)
        self._submit_answer()

    def _refresh_option_styles(self, q: dict) -> None:
        if q["type"] == "判断题":
            for v, btn in self.option_buttons.items():
                if v == self.current_judge:
                    btn.configure(fg_color=C["sel_bg"], border_color=C["sel_border"],
                                  text_color=C["soft_text"])
                else:
                    btn.configure(fg_color=C["card"], border_color=C["border"],
                                  text_color=C["text"])
        else:
            for letter, btn in self.option_buttons.items():
                if letter in self.current_selection:
                    btn.configure(fg_color=C["sel_bg"], border_color=C["sel_border"],
                                  text_color=C["soft_text"])
                else:
                    btn.configure(fg_color=C["card"], border_color=C["border"],
                                  text_color=C["text"])

    def _highlight_options(self, q: dict, user_ans: str) -> None:
        correct = (q.get("answer") or "").upper()
        if q["type"] == "判断题":
            correct_v = norm_judge(q.get("answer"))
            for v, btn in self.option_buttons.items():
                if v == correct_v:
                    btn.configure(fg_color=C["green_bg"], border_color=C["green_border"],
                                  text_color=C["green"])
                elif user_ans and v == user_ans and v != correct_v:
                    btn.configure(fg_color=C["red_bg"], border_color=C["red_border"],
                                  text_color=C["red"])
                else:
                    btn.configure(fg_color=C["card"], border_color=C["border"],
                                  text_color=C["text"])
        else:
            user_set = set(user_ans.upper())
            correct_set = set(correct)
            for letter, btn in self.option_buttons.items():
                if letter in correct_set:
                    btn.configure(fg_color=C["green_bg"], border_color=C["green_border"],
                                  text_color=C["green"])
                elif letter in user_set and letter not in correct_set:
                    btn.configure(fg_color=C["red_bg"], border_color=C["red_border"],
                                  text_color=C["red"])
                else:
                    btn.configure(fg_color=C["card"], border_color=C["border"],
                                  text_color=C["text"])

    def _render_explanation_objective(self, q: dict, user_ans: str, correct: bool) -> None:
        self.explain_box.configure(state="normal")
        self.explain_box.delete("1.0", "end")
        verdict = "✓ 回答正确" if correct else "✗ 回答错误"
        lines = [
            f"{verdict}    你的答案：{user_ans or '（未答）'}    标准答案：{q.get('answer','')}",
            "",
            q.get("explanation") or "（题库未提供解析）",
        ]
        self.explain_box.insert("1.0", "\n".join(lines))
        self.explain_box.configure(state="disabled")

    def _submit_answer(self) -> None:
        if self.answer_submitted or not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if is_subjective(q):
            return
        if q["type"] == "判断题":
            if not self.current_judge:
                return
            user_ans = self.current_judge
        else:
            if not self.current_selection:
                return
            user_ans = "".join(sorted(self.current_selection))
        correct = is_correct(q, user_ans)
        record_answer(self.progress, q["id"], correct, user_ans)
        self.progress["last"]["index"] = self.current_idx
        self._save()
        self.answer_submitted = True
        self._highlight_options(q, user_ans)
        self._render_explanation_objective(q, user_ans, correct)
        self._update_action_buttons_objective()
        self._render_score_only()

    # ------------------------------------------------------------------
    # 主观题分支
    # ------------------------------------------------------------------
    def _render_subjective(self, q: dict) -> None:
        self.answer_submitted = False
        self.subj_ref_shown = False

        stem_card = self._card(self.body, accent=True)
        stem_card.pack(fill="x", pady=(0, 8))
        self.stem_box = ctk.CTkTextbox(
            stem_card, height=self._stem_height(q["stem"]),
            font=_f(15),
            wrap="char", activate_scrollbars=True,
            fg_color=C["card"], border_width=0,
        )
        self.stem_box.pack(fill="x", padx=(8, 14), pady=(2, 8))
        self.stem_box.insert("1.0", q["stem"])
        self.stem_box.configure(state="disabled")

        ctk.CTkLabel(
            self.body, text="✏️ 你的作答",
            font=_f(12, "bold"),
            text_color=C["text_sub"],
            anchor="w",
        ).pack(fill="x", pady=(2, 4))

        answer_card = self._card(self.body)
        answer_card.pack(fill="x", pady=(0, 8))
        self.user_answer_box = ctk.CTkTextbox(
            answer_card, height=140,
            font=_f(14),
            wrap="char", activate_scrollbars=True,
            fg_color=C["card"], border_width=0,
        )
        self.user_answer_box.pack(fill="x", padx=16, pady=(4, 12))

        rec = self._answer_record(q["id"])
        if rec and rec.get("user_answer"):
            self.user_answer_box.insert("1.0", rec.get("user_answer", ""))

        action_row = ctk.CTkFrame(self.body, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 4))

        self.btn_show_ref = btn_primary(
            action_row, text="显示参考答案",
            font=_f(13, "bold"),
            height=40, width=140, corner_radius=12,
            command=self._show_reference_answer,
        )
        self.btn_show_ref.pack(side="left", padx=(0, 6))

        self.btn_mark_correct = ctk.CTkButton(
            action_row, text="我答对了",
            font=_f(13, "bold"),
            height=40, width=106, corner_radius=12,
            fg_color=C["green_bg"], hover_color=C["green_border"],
            text_color=C["green"],
            command=lambda: self._self_mark(True),
        )
        self.btn_mark_correct.pack(side="left", padx=(0, 4))

        self.btn_mark_wrong = ctk.CTkButton(
            action_row, text="我答错了",
            font=_f(13, "bold"),
            height=40, width=106, corner_radius=12,
            fg_color=C["red_bg"], hover_color=C["red_border"],
            text_color=C["red"],
            command=lambda: self._self_mark(False),
        )
        self.btn_mark_wrong.pack(side="left", padx=(0, 8))

        self.btn_redo = btn_ghost(
            action_row, text="清空作答 (R)",
            font=_f(12),
            height=40, width=110, corner_radius=12,
            command=self._redo_current,
        )
        self.btn_redo.pack(side="left", padx=(0, 8))

        self.btn_next = btn_ghost(
            action_row, text="下一题 →",
            font=_f(13),
            height=40, width=110, corner_radius=12,
            command=self._next_q,
        )
        self.btn_next.pack(side="right", padx=(4, 0))
        self.btn_prev = btn_ghost(
            action_row, text="← 上一题",
            font=_f(13),
            height=40, width=110, corner_radius=12,
            command=self._prev_q,
        )
        self.btn_prev.pack(side="right")

        explain_card = self._card(self.body)
        explain_card.pack(fill="both", expand=True, pady=(8, 0))
        ctk.CTkLabel(explain_card, text="💡 参考答案 / 解析", font=_f(12, "bold"),
                     text_color=C["brand"], anchor="w").pack(fill="x", padx=20, pady=(12, 0))
        self.explain_box = ctk.CTkTextbox(
            explain_card, height=160,
            font=_f(13),
            wrap="char",
            fg_color=C["card"], border_width=0,
        )
        self.explain_box.pack(fill="both", expand=True, padx=20, pady=(4, 14))

        self.explain_box.configure(state="normal")
        self.explain_box.delete("1.0", "end")
        if rec:
            self.answer_submitted = True
            self.subj_ref_shown = True
            self._render_subjective_result(q, rec)
        else:
            self.explain_box.insert("1.0", "作答完成后，点击「显示参考答案」对照检查；再点「我答对 / 我答错」记录结果。")
            self.explain_box.configure(state="disabled")

        self._update_action_buttons_subjective()

    def _update_action_buttons_subjective(self) -> None:
        if self.current_idx == 0:
            self.btn_prev.configure(state="disabled")
        else:
            self.btn_prev.configure(state="normal")
        if self.current_idx >= len(self.current_qids) - 1:
            self.btn_next.configure(text="完成 ✓")
        else:
            self.btn_next.configure(text="下一题 →")
        if self.answer_submitted:
            self.btn_mark_correct.configure(state="disabled")
            self.btn_mark_wrong.configure(state="disabled")
            self.btn_show_ref.configure(text="已显示参考答案", state="disabled")
        else:
            if self.subj_ref_shown:
                self.btn_show_ref.configure(text="已显示参考答案", state="disabled")
            else:
                self.btn_show_ref.configure(text="显示参考答案", state="normal")
            self.btn_mark_correct.configure(state="normal")
            self.btn_mark_wrong.configure(state="normal")

    def _show_reference_answer(self) -> None:
        if not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if not is_subjective(q):
            return
        ref = (q.get("explanation") or "").strip() or "（题库未提供参考答案，请对照原书查看）"
        self.explain_box.configure(state="normal")
        self.explain_box.delete("1.0", "end")
        self.explain_box.insert("1.0", ref)
        self.explain_box.configure(state="disabled")
        self.subj_ref_shown = True
        self._update_action_buttons_subjective()

    def _self_mark(self, correct: bool) -> None:
        if not self.current_qids or self.answer_submitted:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if not is_subjective(q):
            return
        user_text = self.user_answer_box.get("1.0", "end").strip()
        record_answer(self.progress, q["id"], correct, user_text)
        self.progress["last"]["index"] = self.current_idx
        self._save()
        self.answer_submitted = True
        # 自动显示参考答案
        if not self.subj_ref_shown:
            self._show_reference_answer()
        self._render_subjective_result(q, {"correct": correct, "user_answer": user_text})
        self._update_action_buttons_subjective()
        self._render_score_only()

    def _render_subjective_result(self, q: dict, rec: dict) -> None:
        self.explain_box.configure(state="normal")
        self.explain_box.delete("1.0", "end")
        verdict = "✓ 已记录：答对" if rec.get("correct") else "✗ 已记录：答错（已加入错题本）"
        ref = (q.get("explanation") or "").strip() or "（题库未提供参考答案，请对照原书查看）"
        lines = [verdict, "", ref]
        self.explain_box.insert("1.0", "\n".join(lines))
        self.explain_box.configure(state="disabled")
        self.subj_ref_shown = True

    # ------------------------------------------------------------------
    # 通用动作
    # ------------------------------------------------------------------
    def _redo_current(self) -> None:
        if not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        clear_answer(self.progress, q["id"])
        self._save()
        self._render_current()

    def _toggle_favorite_current(self) -> None:
        if not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        is_fav = toggle_favorite(self.progress, q["id"])
        self._save()
        self.btn_fav.configure(text=("★ 已收藏" if is_fav else "☆ 收藏 (F)"))

    def _goto_question(self) -> None:
        if not self.current_qids:
            return
        total = len(self.current_qids)
        val = simpledialog.askinteger(
            "题号跳转", f"输入要跳转的序号（1 - {total}）：",
            parent=self, minvalue=1, maxvalue=total,
            initialvalue=self.current_idx + 1,
        )
        if val is None:
            return
        self.current_idx = val - 1
        self.progress["last"]["index"] = self.current_idx
        self._save()
        self._render_current()

    def _render_score_only(self) -> None:
        right = 0
        ans_count = 0
        for qid in self.current_qids:
            rec = self.progress["answered"].get(qid)
            if rec:
                ans_count += 1
                if rec.get("correct"):
                    right += 1
        rate = (right / ans_count * 100) if ans_count else 0.0
        total = len(self.current_qids)
        idx_disp = self.current_idx + 1
        self.lbl_score.configure(
            text=f"{idx_disp} / {total}    已答 {ans_count}    正确率 {rate:.1f}%"
        )
        if total > 0:
            self.progress_bar.set(idx_disp / total)

    def _next_q(self) -> None:
        if not self.current_qids:
            return
        if self.current_idx >= len(self.current_qids) - 1:
            messagebox.showinfo("完成", "本次刷题已完成 ✓\n回到主菜单查看战绩吧！")
            self._back_home()
            return
        self.current_idx += 1
        self.progress["last"]["index"] = self.current_idx
        self._save()
        self._render_current()

    def _prev_q(self) -> None:
        if self.current_idx <= 0:
            return
        self.current_idx -= 1
        self.progress["last"]["index"] = self.current_idx
        self._save()
        self._render_current()

    def _back_home(self) -> None:
        self._save()
        self.current_qids = []
        self._show_page("home")

    # ------------------------------------------------------------------
    # 错题本 / 收藏 / 章节统计 面板
    # ------------------------------------------------------------------
    def _open_wrongbook(self) -> None:
        qids = list(self.progress.get("wrong_book", []))
        # 按当前书本过滤
        if self.current_book_id:
            qids = [qid for qid in qids
                    if self.qmap.get(qid, {}).get("book_id") == self.current_book_id]
        # v3.1: 最近答错的排前面（原为收录顺序）
        ans = self.progress.get("answered", {})
        qids.sort(key=lambda x: -(ans.get(x, {}).get("ts") or 0))
        book_name = book_id_to_name(self.current_book_id) if self.current_book_id else ALL_BOOK
        self._open_qlist_panel(
            title=f"错题本 · {book_name}",
            qids=qids,
            empty_text="目前没有错题，继续加油！🌸",
            start_label="进入错题重练",
            extra_actions=[("清空错题本", self._on_clear_wrongbook)],
            mode_label="错题重练",
            nav="wrongbook",
        )

    def _on_clear_wrongbook(self) -> None:
        scope = "当前书本的" if self.current_book_id else ""
        if not messagebox.askyesno("确认", f"清空{scope}错题本？答题历史不会被清除。"):
            return
        if self.current_book_id:
            # 仅清除当前书本范围内的错题
            keep = [qid for qid in self.progress.get("wrong_book", [])
                    if self.qmap.get(qid, {}).get("book_id") != self.current_book_id]
            self.progress["wrong_book"] = keep
        else:
            self.progress["wrong_book"] = []
        self._save()
        self._show_page("wrongbook", self._open_wrongbook)

    def _open_favorites(self) -> None:
        qids = list(self.progress.get("favorites", []))
        # 按当前书本过滤
        if self.current_book_id:
            qids = [qid for qid in qids
                    if self.qmap.get(qid, {}).get("book_id") == self.current_book_id]
        book_name = book_id_to_name(self.current_book_id) if self.current_book_id else ALL_BOOK
        self._open_qlist_panel(
            title=f"收藏夹 · {book_name}",
            qids=qids,
            empty_text="还没有收藏的题目。\n答题时按 F 或点右上角 ☆ 即可收藏。",
            start_label="进入收藏练习",
            extra_actions=[("清空收藏", self._on_clear_favorites)],
            mode_label="收藏题",
            nav="favorites",
        )

    def _on_clear_favorites(self) -> None:
        scope = "当前书本的" if self.current_book_id else "所有"
        if not messagebox.askyesno("确认", f"清空{scope}收藏？"):
            return
        if self.current_book_id:
            keep = [qid for qid in self.progress.get("favorites", [])
                    if self.qmap.get(qid, {}).get("book_id") != self.current_book_id]
            self.progress["favorites"] = keep
        else:
            self.progress["favorites"] = []
        self._save()
        self._show_page("favorites", self._open_favorites)

    def _page_header(self, title: str, subtitle: str = "") -> None:
        """二级页面统一页头：大标题 + 副标题（侧边栏已承担导航）。"""
        ctk.CTkLabel(self.page_area, text=title,
                     font=_f(22, "bold"), text_color=C["text"],
                     anchor="w").pack(fill="x", padx=36, pady=(24, 0))
        if subtitle:
            ctk.CTkLabel(self.page_area, text=subtitle,
                         font=_f(12), text_color=C["text_sub"],
                         anchor="w").pack(fill="x", padx=36, pady=(2, 0))

    def _open_qlist_panel(self, *, title: str, qids: list[str], empty_text: str,
                          start_label: str, extra_actions: list, mode_label: str,
                          nav: str = "") -> None:
        self._clear()
        nav_key = nav or ("wrongbook" if title.startswith("错题本") else "favorites")
        self._set_active_nav(nav_key)

        has_q = bool(qids)
        head_row = ctk.CTkFrame(self.page_area, fg_color="transparent")
        head_row.pack(fill="x", padx=36, pady=(14, 10))
        ctk.CTkLabel(head_row, text=f"{title}（共 {len(qids)} 道）",
                     font=_f(16, "bold"), text_color=C["text"],
                     anchor="w").pack(side="left")

        if has_q:
            btn_primary(
                head_row, text=start_label, height=36, corner_radius=12,
                font=_f(13, "bold"),
                command=lambda: self._start_qids(qids, mode=mode_label),
            ).pack(side="right", padx=(4, 0))
            for label, cmd in extra_actions:
                btn_ghost(
                    head_row, text=label, height=36, corner_radius=12,
                    font=_f(12),
                    command=cmd,
                ).pack(side="right", padx=4)
        else:
            ctk.CTkLabel(self.page_area, text=empty_text, font=_f(14),
                         text_color=C["text_sub"], justify="left").pack(pady=48)
            return

        list_frame = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=36, pady=(0, 14))

        for i, qid in enumerate(qids):
            q = self.qmap.get(qid)
            if not q:
                continue
            row = ctk.CTkFrame(list_frame, corner_radius=14,
                               fg_color=C["card"], border_width=1,
                               border_color=C["border"])
            row.pack(fill="x", pady=3)
            badge = "主观题" if is_subjective(q) else q["type"]
            head = f"#{i+1}  {self._chapter_label(q)} · {badge} · 第 {q['num'] + 1} 题"
            ctk.CTkLabel(row, text=head, font=_f(11),
                         text_color=C["text_sub"],
                         anchor="w", justify="left").pack(fill="x", padx=18, pady=(10, 0))
            stem = q["stem"]
            if len(stem) > 120:
                stem = stem[:120] + " ..."
            ctk.CTkLabel(row, text=stem, font=_f(13),
                         text_color=C["text"],
                         anchor="w", justify="left", wraplength=860).pack(
                fill="x", padx=18, pady=(2, 4))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(fill="x", padx=18, pady=(0, 10))
            btn_primary(
                actions, text="单题练习", height=28, width=84, corner_radius=9,
                font=_f(11, "bold"),
                command=lambda qq=qid: self._start_qids([qq], mode="单题"),
            ).pack(side="left", padx=(0, 4))
            btn_ghost(
                actions, text="移除", height=28, width=60, corner_radius=9,
                font=_f(11),
                command=lambda qq=qid, t=title: self._remove_from_collection(t, qq),
            ).pack(side="left")
            ans_rec = self.progress["answered"].get(qid)
            if ans_rec:
                tag = "已答对" if ans_rec.get("correct") else "答错"
                color = C["green"] if ans_rec.get("correct") else C["red"]
                ctk.CTkLabel(actions, text=tag, font=_f(11, "bold"),
                             text_color=color).pack(side="right")

    def _remove_from_collection(self, title: str, qid: str) -> None:
        if title.startswith("错题本"):
            if qid in self.progress["wrong_book"]:
                self.progress["wrong_book"].remove(qid)
            self._save()
            self._show_page("wrongbook", self._open_wrongbook)
        else:
            if qid in self.progress["favorites"]:
                self.progress["favorites"].remove(qid)
            self._save()
            self._show_page("favorites", self._open_favorites)

    def _open_chapter_stats(self) -> None:
        self._page_header("📊 学习统计", "按书本与章节查看进度和正确率。")

        body = ctk.CTkScrollableFrame(self.page_area, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=36, pady=(12, 0))

        # 若选择"全部书本"，按书本分组展示书本汇总 + 章节
        if not self.current_book_id:
            book_stats = book_progress(self.progress, self.questions)
            ch_stats_all = chapter_progress(self.progress, self.questions)
            # 按 book_id 聚合章节
            ch_by_book: dict[str, list[dict]] = {}
            for st in ch_stats_all:
                bid = st.get("book_id") or ""
                ch_by_book.setdefault(bid, []).append(st)
            for b in book_stats:
                bid = b["book_id"]
                # 书本汇总卡
                head = ctk.CTkFrame(body, corner_radius=16,
                                    fg_color=C["soft"], border_width=1,
                                    border_color=C["soft_border"])
                head.pack(fill="x", pady=(8, 4))
                line1 = ctk.CTkFrame(head, fg_color="transparent")
                line1.pack(fill="x", padx=20, pady=(13, 4))
                ctk.CTkLabel(
                    line1, text=f"{b['name']}",
                    font=_f(14, "bold"),
                    text_color=C["soft_text"],
                    anchor="w",
                ).pack(side="left")
                ctk.CTkLabel(
                    line1,
                    text=(f"  共 {b['total']} 道  ·  已答 {b['answered']}  ·  "
                          f"正确率 {b['rate']:.1f}%  ·  错题 {b['wrong']}  ·  收藏 {b['fav']}"),
                    font=_f(11),
                    text_color=C["text_sub"],
                ).pack(side="left")
                btn_primary(
                    line1, text="刷整本", height=30, width=84, corner_radius=10,
                    font=_f(11, "bold"),
                    command=lambda bid_=bid: self._start_book(bid_),
                ).pack(side="right")
                bar = ctk.CTkProgressBar(head, height=6, corner_radius=1000)
                bar.pack(fill="x", padx=20, pady=(0, 13))
                bar.set((b["answered"] / b["total"]) if b["total"] else 0)
                # 该书的章节
                for st in ch_by_book.get(bid, []):
                    self._render_chapter_row(body, st)
        else:
            stats = chapter_progress(self.progress, self.questions, self.current_book_id)
            if not stats:
                ctk.CTkLabel(body, text="当前书本下没有章节统计。",
                             font=_f(14)).pack(pady=40)
                return
            for st in stats:
                self._render_chapter_row(body, st)
        # 底部留白
        ctk.CTkLabel(body, text="", font=_f(1)).pack(pady=8)

    def _render_chapter_row(self, parent, st: dict) -> None:
        row = ctk.CTkFrame(parent, corner_radius=14,
                           fg_color=C["card"], border_width=1,
                           border_color=C["border"])
        row.pack(fill="x", pady=3)
        line1 = ctk.CTkFrame(row, fg_color="transparent")
        line1.pack(fill="x", padx=20, pady=(10, 2))
        ctk.CTkLabel(line1, text=st["name"], font=_f(13, "bold"),
                     text_color=C["text"],
                     anchor="w").pack(side="left")
        ctk.CTkLabel(
            line1,
            text=(f"  共 {st['total']} 道  ·  已答 {st['answered']}  ·  "
                  f"正确 {st['right']}  ·  正确率 {st['rate']:.1f}%"),
            font=_f(11),
            text_color=C["text_sub"],
        ).pack(side="left")
        btn_soft(
            line1, text="刷本章", height=28, width=84, corner_radius=10,
            font=_f(11, "bold"),
            command=lambda name=st["name"]: self._start_chapter(name),
        ).pack(side="right")
        bar = ctk.CTkProgressBar(row, height=5, corner_radius=1000)
        bar.pack(fill="x", padx=20, pady=(0, 11))
        bar.set((st["answered"] / st["total"]) if st["total"] else 0)

    def _start_book(self, book_id: str) -> None:
        qids = [q["id"] for q in self.questions if q.get("book_id") == book_id]
        bn = book_id_to_name(book_id) or book_id
        self._start_qids(qids, mode=f"整本 · {bn}")

    def _start_chapter(self, chapter_name: str) -> None:
        qids = [q["id"] for q in self.questions
                if self._chapter_label(q) == chapter_name]
        self._start_qids(qids, mode=f"章节 · {chapter_name}")

    # ------------------------------------------------------------------
    # 全局快捷键
    # ------------------------------------------------------------------
    def _bind_global_keys(self) -> None:
        for k in ("<Key-1>", "<Key-2>", "<Key-3>", "<Key-4>", "<Key-5>", "<Key-6>", "<Key-7>"):
            self.bind(k, self._on_number_key)
        self.bind("<space>", lambda e: self._key_action(self._next_q))
        self.bind("<Right>", lambda e: self._key_action(self._next_q))
        self.bind("<Left>", lambda e: self._key_action(self._prev_q))
        self.bind("<BackSpace>", lambda e: self._key_action(self._prev_q))
        self.bind("<Return>", lambda e: self._key_action(self._submit_or_next))
        self.bind("<Escape>", lambda e: self._escape_action())
        self.bind("<Key-f>", lambda e: self._key_action(self._toggle_favorite_current))
        self.bind("<Key-F>", lambda e: self._key_action(self._toggle_favorite_current))
        self.bind("<Key-r>", lambda e: self._key_action(self._redo_current))
        self.bind("<Key-R>", lambda e: self._key_action(self._redo_current))
        self.bind("<Key-g>", lambda e: self._key_action(self._goto_question))
        self.bind("<Key-G>", lambda e: self._key_action(self._goto_question))

    def _key_action(self, fn) -> None:
        """快捷键派发。当输入框聚焦时让位给输入框默认行为。"""
        if not self.current_qids:
            return
        if self._input_has_focus():
            return
        try:
            fn()
        except Exception as e:
            try:
                messagebox.showerror("发生错误", str(e))
            except Exception:
                pass

    def _escape_action(self) -> None:
        """Esc 即便在输入框聚焦时也要能返回主菜单。"""
        if not self.current_qids:
            return
        try:
            self._back_home()
        except Exception:
            pass

    def _submit_or_next(self) -> None:
        if not self.current_qids:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if is_subjective(q):
            # 主观题：未显示参考答案则显示，否则前进
            if not self.subj_ref_shown:
                self._show_reference_answer()
            else:
                self._next_q()
            return
        if not self.answer_submitted:
            self._submit_answer()
        else:
            self._next_q()

    def _on_number_key(self, event) -> None:
        if not self.current_qids:
            return
        if self._input_has_focus():
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if is_subjective(q):
            return
        try:
            n = int(event.keysym)
        except ValueError:
            return
        if q["type"] == "判断题":
            if n == 1:
                self._toggle_judge("√")
            elif n == 2:
                self._toggle_judge("×")
        else:
            mapping = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"}
            letter = mapping.get(n)
            if letter:
                self._toggle_option(letter)


# 页面名 → 方法名映射（getattr 绑定调用；置于类定义后）
App._pages = {
    "home": "_build_home",
    "training": "_open_training",
    "wrongbook": "_open_wrongbook",
    "favorites": "_open_favorites",
    "stats": "_open_chapter_stats",
}


def _icon_path() -> str | None:
    """寻找窗口图标：先打包后 _MEIPASS，再开发环境 assets/。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    for cand in (base / "assets" / "app.ico", base / "app.ico"):
        if cand.exists():
            return str(cand)
    return None


def main() -> None:
    try:
        app = App()
    except Exception as e:
        try:
            from tkinter import Tk
            root = Tk(); root.withdraw()
            messagebox.showerror("启动失败", f"程序无法启动：\n{e}")
            root.destroy()
        except Exception:
            print("启动失败:", e)
        return
    ico = _icon_path()
    if ico:
        try:
            app.iconbitmap(ico)
        except Exception:
            pass
        try:
            # 任务栏图标（部分 Win11 需要）
            from PIL import Image, ImageTk
            png_path = Path(ico).parent / "app_256.png"
            if png_path.exists():
                img = Image.open(png_path)
                photo = ImageTk.PhotoImage(img)
                app.iconphoto(True, photo)
                # 防止被 GC
                app._icon_ref = photo  # type: ignore[attr-defined]
        except Exception:
            pass
    app.mainloop()


if __name__ == "__main__":
    main()
