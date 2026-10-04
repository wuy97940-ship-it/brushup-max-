"""财管经营篇桌面页面；所有状态变更交给 AdventureApp 的原子保存入口。"""
from __future__ import annotations

import copy
import time
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

import finance
import game
import store
from app import C, _f, btn_ghost, btn_primary, btn_soft


def analysis_text(question: dict) -> str:
    analysis = question.get("analysis") or {}
    lines = []
    for key, title in (("position", "考点定位"), ("principle", "原理解释"),
                       ("formulas", "公式与条件"), ("steps", "逐步分析"),
                       ("option_analysis", "逐项分析"), ("units", "单位与精度"),
                       ("pitfalls", "易错提醒"), ("memory", "记忆提示")):
        value = analysis.get(key)
        if not value:
            continue
        if isinstance(value, dict):
            value = "\n".join(f"{k}：{v}" for k, v in value.items())
        elif isinstance(value, list):
            value = "\n".join(str(v) for v in value)
        lines.extend([title, str(value), ""])
    return "\n".join(lines).strip()


class FinanceUIMixin:
    def _finance_question(self):
        if not self.current_qids:
            return None
        q = self.qmap[self.current_qids[self.current_idx]]
        return q if q.get("subquestions") else None

    def _finance_attempt(self, progress=None):
        p = progress if progress is not None else self.progress
        return p["game"]["active"] if self._game_mode else p.get("practice")

    def _finance_image(self, parent, relative, size=128):
        path = store.resource_path("assets/" + relative)
        if not path.is_file():
            return None
        with Image.open(path) as original:
            im = original.convert("RGBA")
        icon = ctk.CTkImage(im, size=(size, size))
        label = ctk.CTkLabel(parent, text="", image=icon)
        label._finance_image = icon
        return label

    def _finance_source_images(self, question, kind="stem_images"):
        for relative in question.get(kind, []):
            path = store.resource_path("assets/" + relative)
            if not path.is_file():
                continue
            with Image.open(path) as original:
                im = original.convert("RGB")
            width = min(850, max(320, self.winfo_width() - 330), im.width)
            height = max(1, round(im.height * width / im.width))
            picture = ctk.CTkImage(im, size=(width, height))
            label = ctk.CTkLabel(self.body, text="", image=picture)
            label._finance_image = picture
            label.pack(pady=8)
            btn_ghost(self.body, text="放大图表", height=28,
                      command=lambda p=path: self._finance_zoom(p)).pack(pady=(0, 8))

    def _finance_zoom(self, path: Path):
        window = ctk.CTkToplevel(self)
        window.title("题目图表")
        window.geometry("1000x760")
        panel = ctk.CTkScrollableFrame(window, fg_color=C["card"])
        panel.pack(fill="both", expand=True)
        with Image.open(path) as original:
            im = original.convert("RGB")
        width = min(930, im.width)
        picture = ctk.CTkImage(im, size=(width, round(im.height * width / im.width)))
        label = ctk.CTkLabel(panel, text="", image=picture)
        label._finance_image = picture
        label.pack(pady=12)

    def _render_explanation_objective(self, q, user_ans, correct):
        super()._render_explanation_objective(q, user_ans, correct)
        extra = analysis_text(q)
        if extra:
            self.explain_box.configure(state="normal")
            self.explain_box.insert("end", "\n\n扩展讲解\n" + extra)
            self.explain_box.configure(state="disabled")
        self._finance_source_images(q, "reference_images")

    def _render_objective(self, q):
        rendered = q
        if q.get("stem_images_primary") and q.get("stem_images"):
            rendered = {**q, "stem": "请阅读下方原题图示，按图中的选项选择答案。", "options": {letter: f"选项 {letter}（见题目图示）" for letter in q.get("options", {})}}
        super()._render_objective(rendered)
        if any(line.count("|") >= 2 for line in rendered["stem"].splitlines()):
            self.stem_box.configure(wrap="none")
        self._finance_source_images(q)

    def _render_finance_subjective(self, question):
        attempt = self._finance_attempt()
        current = finance.draft(attempt, question)
        submission = attempt.get("structured_submissions", {}).get(question["id"])
        correction = bool(attempt.get("correction_edit", {}).get(question["id"]))
        self.answer_submitted = question["id"] in attempt["answers"] and not correction
        self.subj_ref_shown = bool(submission)
        frozen = bool(submission)
        card = self._card_frame(self.body)
        card.pack(fill="x", pady=(0, 8))
        rendered_stem = "完整题目资料、表格与公式见下方原题图示。" if question.get("stem_images_primary") and question.get("stem_images") else question["stem"]
        stem = ctk.CTkTextbox(card, height=self._stem_height(rendered_stem), font=_f(15),
                             wrap="none" if any(line.count("|") >= 2 for line in rendered_stem.splitlines()) else "char",
                             fg_color=C["card"], border_width=0)
        stem.pack(fill="x", padx=15, pady=10)
        stem.insert("1.0", rendered_stem)
        stem.configure(state="disabled")
        self._finance_source_images(question)
        self._finance_process_boxes, self._finance_value_entries, self._finance_unit_vars = {}, {}, {}
        self._finance_process_vars = {}
        snapshot = submission["draft"] if submission else current
        for sub in question["subquestions"]:
            card = self._card_frame(self.body)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(card, text=f"小问 {sub['id']}  {sub['prompt']}", font=_f(13, "bold"),
                         wraplength=820, justify="left", anchor="w").pack(fill="x", padx=16, pady=(12, 5))
            box = ctk.CTkTextbox(card, height=110, font=_f(13), wrap="char", fg_color=C["card"])
            box.pack(fill="x", padx=16, pady=(0, 10))
            box.insert("1.0", snapshot["process"].get(sub["id"], ""))
            box.configure(state="disabled" if frozen else "normal")
            box.bind("<KeyRelease>", self._on_draft_key, add="+")
            self._finance_process_boxes[sub["id"]] = box
            for check in question.get("numeric_checks", []):
                if check["key"] not in sub.get("checks", []):
                    continue
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=(0, 9))
                ctk.CTkLabel(row, text=check["label"], font=_f(12), anchor="w",
                             wraplength=400).pack(side="left", padx=(0, 12))
                entry = ctk.CTkEntry(row, width=150, placeholder_text="填写关键数值")
                entry.pack(side="left", padx=(0, 8))
                entry.insert(0, snapshot["values"].get(check["key"], ""))
                entry.bind("<KeyRelease>", self._on_draft_key, add="+")
                entry.configure(state="disabled" if frozen else "normal")
                self._finance_value_entries[check["key"]] = entry
                unit = check.get("unit") or "无单位"
                choices = ["元", "万元"] if unit in ("元", "万元") else ["%", "小数"] if unit in ("%", "小数") else [unit]
                variable = ctk.StringVar(value=snapshot["units"].get(check["key"]) or unit)
                menu = ctk.CTkOptionMenu(row, values=choices, variable=variable, width=95,
                                       command=lambda _value: self._on_draft_key())
                menu.pack(side="left")
                menu.configure(state="disabled" if frozen else "normal")
                self._finance_unit_vars[check["key"]] = variable
            if submission:
                reference = ctk.CTkTextbox(card, height=150, font=_f(13), wrap="char", fg_color=C["card"])
                reference.pack(fill="x", padx=16, pady=5)
                reference.insert("1.0", "参考过程\n" + sub["reference"] + "\n\n过程核对\n" + "\n".join(sub.get("process_checklist", [])))
                reference.configure(state="disabled")
                value = submission["process"].get(sub["id"])
                variable = ctk.StringVar(value="过程正确" if value is True else "需要复盘" if value is False else "选择过程自评")
                choice = ctk.CTkOptionMenu(card, values=["选择过程自评", "过程正确", "需要复盘"], variable=variable,
                    command=lambda value, sid=sub["id"]: self._finance_set_process(sid, value))
                choice.pack(anchor="w", padx=16, pady=(5, 12))
                if submission["graded"]:
                    choice.configure(state="disabled")
                self._finance_process_vars[sub["id"]] = variable
        if submission:
            card = self._card_frame(self.body)
            card.pack(fill="x", pady=8)
            verdicts = [f"{'✓' if c['correct'] else '✗'} {c['label']}：{c['message']}；参考 {c['expected']} {c['unit']}" for c in submission["checks"]]
            if not verdicts:
                verdicts = ["本题通过逐小问过程自评记录成绩。"]
            ctk.CTkLabel(card, text="数值核对\n" + "\n".join(verdicts), font=_f(13), justify="left",
                         wraplength=820, anchor="w").pack(fill="x", padx=16, pady=12)
            ref = ctk.CTkTextbox(card, height=240, font=_f(13), wrap="char", fg_color=C["card"])
            ref.pack(fill="x", padx=16, pady=(0, 12))
            ref.insert("1.0", "原参考答案与解析\n" + (question.get("explanation") or question.get("answer", "")) + "\n\n扩展讲解\n" + analysis_text(question))
            ref.configure(state="disabled")
            self.explain_box = ref
            for index, text in enumerate(attempt.get("outlines", {}).get(question["id"], []), 1):
                ctk.CTkLabel(card, text=f"答题卡 {index} · {text}", font=_f(12), wraplength=820,
                             justify="left", anchor="w").pack(fill="x", padx=16, pady=6)
            self._finance_source_images(question, "reference_images")
        actions = ctk.CTkFrame(self.body, fg_color="transparent")
        actions.pack(fill="x", pady=12)
        if not submission:
            btn_primary(actions, text="提交小问并查看推导", height=40,
                        command=self._finance_submit).pack(side="left", padx=(0, 8))
        elif not submission["graded"]:
            btn_primary(actions, text="保存本次核对结果", height=40,
                        command=self._finance_grade).pack(side="left", padx=(0, 8))
        else:
            result = submission["record"]
            ctk.CTkLabel(actions, text=("✓ 本次全部通过" if result["correct"] else "✗ 本次仍需复盘") +
                (" · 纠正练习" if submission["correction"] else " · 首次成绩已记录"), font=_f(12, "bold")).pack(side="left", padx=(0, 10))
            btn_soft(actions, text="重新核对", command=self._finance_correct).pack(side="left")
        self.btn_prev = btn_ghost(actions, text="← 上一题", command=self._prev_q)
        self.btn_prev.pack(side="right", padx=5)
        self.btn_next = btn_ghost(actions, text="结算本关 ✓" if self._game_mode and self.current_idx == len(self.current_qids)-1 else "完成 ✓" if self.current_idx == len(self.current_qids)-1 else "下一题 →", command=self._next_q)
        self.btn_next.pack(side="right")
        self.btn_prev.configure(state="normal" if self.current_idx else "disabled")
        self.btn_next.configure(state="normal" if self.answer_submitted else "disabled")
        if correction:
            ctk.CTkLabel(self.body, text="纠正练习会单独保存，首次提交成绩保持原记录。", font=_f(11), text_color=C["text_sub"]).pack(pady=4)

    def _finance_capture(self):
        return {"process": {key: box.get("1.0", "end").strip() for key, box in self._finance_process_boxes.items()},
                "values": {key: box.get().strip() for key, box in self._finance_value_entries.items()},
                "units": {key: variable.get() for key, variable in self._finance_unit_vars.items()}}

    def _flush_finance_draft(self):
        question = self._finance_question()
        attempt = self._finance_attempt()
        if not question or not attempt or self._pending_transaction or attempt.get("structured_submissions", {}).get(question["id"]):
            return
        if not self._finance_process_boxes or any(not b.winfo_exists() for b in self._finance_process_boxes.values()):
            return
        snapshot = self._finance_capture()
        if snapshot != finance.draft(attempt, question):
            self._commit(lambda p: self._finance_attempt(p).setdefault("structured_drafts", {}).update({question["id"]: snapshot}))

    def _finance_submit(self):
        question, snapshot = self._finance_question(), self._finance_capture()
        def mutate(p):
            a = self._finance_attempt(p)
            a.setdefault("structured_drafts", {})[question["id"]] = snapshot
            result = finance.prepare_submission(a, question)
            a["drafts"][question["id"]] = "\n".join(snapshot["process"].values())
            return result
        if self._commit(mutate):
            self._render_current()

    def _finance_set_process(self, sub_id, value):
        q = self._finance_question()
        def mutate(p):
            submission = self._finance_attempt(p)["structured_submissions"][q["id"]]
            if value == "选择过程自评":
                submission["process"].pop(sub_id, None)
            else:
                submission["process"][sub_id] = value == "过程正确"
        if not self._commit(mutate):
            self._render_current()

    def _finance_grade(self):
        q = self._finance_question()
        def mutate(p):
            result = finance.grade(self._finance_attempt(p), q)
            if result["first"]:
                rec = result["record"]
                store.record_answer(p, q["id"], rec["correct"], rec["user_answer"])
            return result
        if self._commit(mutate):
            self._render_current()

    def _finance_correct(self):
        q = self._finance_question()
        if self._commit(lambda p: finance.begin_correction(self._finance_attempt(p), q)):
            self._render_current()

    def _build_finance_town(self):
        self._game_mode = False
        model = finance.view(self.g)
        frame = self._scroll()
        self._heading(frame, "星光经营小镇", f"建材 {model['materials']} 份 · 每章首通获得3份，完整20章可建满六座三级建筑")
        shortcuts = ctk.CTkFrame(frame, fg_color="transparent")
        shortcuts.pack(fill="x", pady=(0, 12))
        for label, action in (("公式图鉴", self._build_finance_formulas), ("经营委托", self._build_finance_commissions),
                              ("错题救援", self._build_finance_rescue), ("伙伴与工具", self._build_finance_companions)):
            btn_soft(shortcuts, text=label, command=lambda b=action: self._show_page("town", b)).pack(side="left", padx=(0, 8))
        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x")
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1, uniform="town")
        for index, building in enumerate(model["buildings"]):
            act = next(a for a in model["acts"] if a["id"] == building["act_id"])
            card = self._card_frame(grid)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=5, pady=7)
            image = self._finance_image(card, building["assets"][max(0, building["level"] - 1)], 140)
            if image:
                image.pack(pady=(8, 0))
            ctk.CTkLabel(card, text=act["name"], font=_f(15, "bold"), text_color=C["brand"]).pack(pady=5)
            ctk.CTkLabel(card, text=f"{building['name']} · {building['level']}/3级\n{act['theme']}", font=_f(11), wraplength=240).pack(pady=5)
            btn_soft(card, text="回看剧情" if act["seen"] else "进入剧情", command=lambda a=act: self._open_finance_story(a["id"])).pack(fill="x", padx=12, pady=5)
            button = btn_primary(card, text="已成为星光地标" if building["level"] == 3 else f"建设升级 · {building['cost']}份建材",
                command=lambda bid=building["id"]: self._finance_build(bid))
            button.pack(fill="x", padx=12, pady=(0, 12))
            if not building["open"] or building["level"] == 3 or model["materials"] < building["cost"]:
                button.configure(state="disabled")
        owned = [p for p in finance.CONFIG["props"] if p["kind"] == "decoration" and p["id"] in self.g["inventory"]]
        if owned:
            self._heading(frame, "小镇摆件", "学习积累的金币，也能点亮小镇的日常")
            shelf = self._card_frame(frame)
            shelf.pack(fill="x", pady=8)
            for item in owned:
                holder = ctk.CTkFrame(shelf, fg_color="transparent")
                holder.pack(side="left", padx=16, pady=12)
                icon = self._finance_image(holder, item["asset"], 90)
                if icon:
                    icon.pack()
                ctk.CTkLabel(holder, text=item["name"], font=_f(11)).pack()

    def _finance_build(self, building_id):
        if self._commit(lambda p: finance.upgrade_building(p, building_id)):
            self._show_page("town")

    def _open_finance_story(self, act_id, after=None):
        try:
            content = finance.story_for(self.g, act_id)
        except ValueError as error:
            messagebox.showinfo("剧情尚未开放", str(error))
            return
        lines = content["story"] + (content["completion_story"] if content["completed"] else [])
        position = [0]
        def finish():
            if self._commit(lambda p: finance.mark_story(p, act_id)):
                after() if after else self._show_page("town")
        def draw():
            self._show_page("town", build)
        def build():
            frame = self._scroll()
            self._heading(frame, content["act"]["name"], f"星光账本 · {position[0]+1}/{len(lines)}")
            cast = self._card_frame(frame)
            cast.pack(fill="x", pady=12)
            for character in ("xiaoyuan", "orange_adventurer", "xiaobao"):
                g = copy.deepcopy(self.g)
                g.update(skin=character, outfit=None)
                ctk.CTkLabel(cast, text="", image=self.sprites.portrait(g, 140, "think")).pack(side="left", padx=18, pady=18)
            npc = next(n for n in finance.CONFIG["npcs"] if n["id"] == (content["act"].get("npc_id") or content["act"].get("npc")))
            icon = self._finance_image(cast, npc["asset"], 130)
            if icon:
                icon.pack(side="right", padx=18)
            line = lines[position[0]]
            dialogue = self._card_frame(frame)
            dialogue.pack(fill="x", pady=10)
            ctk.CTkLabel(dialogue, text=line["speaker"], font=_f(16, "bold"), text_color=C["brand"], anchor="w").pack(fill="x", padx=25, pady=(20, 5))
            ctk.CTkLabel(dialogue, text=line["text"], font=_f(17), wraplength=850, justify="left", anchor="w").pack(fill="x", padx=25, pady=(0, 25))
            def forward():
                if position[0] + 1 == len(lines):
                    finish()
                else:
                    position[0] += 1
                    draw()
            btn_primary(frame, text="开始这一幕" if position[0]+1 == len(lines) else "下一段 →", command=forward).pack(fill="x", pady=6)
            btn_ghost(frame, text="跳过剧情", command=finish).pack(pady=5)
        draw()

    def _build_finance_commissions(self):
        frame = self._scroll()
        self._heading(frame, "经营委托", "帮助六位小镇居民解决问题，领取12张专属明信片")
        for item in finance.view(self.g)["commissions"]:
            card = self._card_frame(frame)
            card.pack(fill="x", pady=5)
            ctk.CTkLabel(card, text=item["name"] + (" · 已领取" if item["claimed"] else ""), font=_f(14, "bold"), anchor="w").pack(fill="x", padx=16, pady=(12, 4))
            ctk.CTkLabel(card, text=item["prompt"], font=_f(12), wraplength=850, justify="left", anchor="w").pack(fill="x", padx=16, pady=5)
            button = btn_soft(card, text="已完成" if item["claimed"] else "接受委托" if item["open"] else "随剧情开放",
                command=lambda cid=item["id"]: self._finance_start_commission(cid))
            button.pack(anchor="e", padx=16, pady=(0, 12))
            if item["claimed"] or not item["open"]:
                button.configure(state="disabled")

    def _finance_start_commission(self, commission_id):
        qids = finance.commission_questions(self.questions, commission_id)
        item = next(c for c in finance.CONFIG["commissions"] if c["id"] == commission_id)
        if len(qids) != item["amount"]:
            messagebox.showinfo("委托准备中", "对应章节的完整题目暂不足，其他委托和学习入口仍可使用。")
            return
        self._start_qids(qids, "经营委托")
        self._commit(lambda p: p["practice"].update(commission_id=commission_id))

    def _build_finance_rescue(self):
        frame = self._scroll()
        self._heading(frame, "错题救援", "带上精灵伙伴，一次复盘当前科目最多5道错题")
        world = self.g["world"]
        qids = finance.rescue_questions(self.progress, self.questions, world)
        companion = finance.state(self.g)["companion"]
        name = game.CATALOG.get(companion, {}).get("name", "小圆")
        card = self._card_frame(frame)
        card.pack(fill="x", pady=12)
        if companion:
            icon = self.sprites.item_icon(companion, 130)
            if icon:
                ctk.CTkLabel(card, text="", image=icon).pack(pady=12)
        ctk.CTkLabel(card, text=f"{name}：这一科的救援已完成，继续前进吧！" if not qids else f"{name}陪你复盘 {len(qids)} 道错题", font=_f(16, "bold"), wraplength=800).pack(padx=20, pady=25)
        if qids:
            def start():
                self._start_qids(qids, "错题救援")
                self._commit(lambda p: p["practice"].update(rescue_world=world, rescue_companion=companion))
            btn_primary(card, text="开始救援", command=start).pack(fill="x", padx=20, pady=(0, 20))
        for entry in reversed(finance.state(self.g)["diary"][-10:]):
            ctk.CTkLabel(frame, text=entry["text"], font=_f(12), anchor="w").pack(fill="x", pady=5)

    def _finance_finish_activity(self):
        a = self.progress.get("practice")
        if not a or not (a.get("commission_id") or a.get("rescue_world")):
            return False
        if any(qid not in a["answers"] for qid in a["qids"]):
            messagebox.showinfo("还有题目待完成", "完成本次全部题目后，再领取明信片或写入伙伴日记。")
            return True
        correct = sum(bool(a["answers"][qid]["correct"]) for qid in a["qids"])
        if a.get("commission_id"):
            if correct * 100 < len(a["qids"]) * game.CONFIG["pass_percent"]:
                messagebox.showinfo("继续复盘", f"本次答对 {correct}/{len(a['qids'])}，达到{game.CONFIG['pass_percent']}%后可领取明信片。")
                self._show_page("town", self._build_finance_commissions)
            elif self._commit(lambda p: finance.claim_commission(p, a["commission_id"], p["practice"])):
                self._show_page("town", self._build_finance_commissions)
        else:
            def diary(p):
                entries = finance.state(p["game"])["diary"]
                if not any(e["attempt_id"] == a["id"] for e in entries):
                    name = game.CATALOG.get(a.get("rescue_companion"), {}).get("name", "小圆")
                    entries.append({"attempt_id": a["id"], "world": a["rescue_world"], "qids": a["qids"],
                                    "text": f"{name}完成了{len(a['qids'])}题救援，答对{correct}题。", "ts": time.time()})
            if self._commit(diary):
                self._show_page("town", self._build_finance_rescue)
        self.current_qids = []
        return True

    def _build_finance_formulas(self):
        frame = self._scroll()
        self._heading(frame, "公式图鉴", "随章节学习开放；公式、符号、条件和误区一起记忆")
        chapter_map = {c["number"]: c for c in finance.chapters(self.g)}
        for chapter in finance.knowledge()["chapters"]:
            number = chapter["chapter_no"]
            open_now = number in chapter_map and game.can_play(self.g, chapter_map[number]["stages"][0])
            lit = bool(finance.state(self.g)["chapter_claims"].get(str(number)))
            reviewed = f"chapter:{number}" in finance.state(self.g)["formula_seen"]
            card = self._card_frame(frame)
            card.pack(fill="x", pady=5)
            ctk.CTkLabel(card, text=f"{'★' if lit else '☆'} 第{number}章  {chapter['title']}", font=_f(13, "bold"), anchor="w").pack(fill="x", padx=16, pady=(12, 6))
            if not open_now:
                ctk.CTkLabel(card, text="完成前面的章节后开放", font=_f(11), text_color=C["text_sub"]).pack(anchor="w", padx=16, pady=(0, 12))
                continue
            formulas = chapter.get("formulas", [])
            lines = []
            for formula in formulas:
                if isinstance(formula, str):
                    lines.append(formula)
                else:
                    symbols = formula.get("symbols", {})
                    if isinstance(symbols, dict):
                        symbols = "；".join(f"{k}：{v}" for k, v in symbols.items())
                    lines.extend([formula.get("name", ""), formula.get("expression", formula.get("formula", "")),
                                  "符号：" + self._finance_readable(symbols),
                                  "适用条件：" + self._finance_readable(formula.get("conditions", "")),
                                  "单位：" + self._finance_readable(formula.get("units", "")),
                                  "易错点：" + self._finance_readable(formula.get("pitfalls", [])),
                                  "记忆提示：" + self._finance_readable(formula.get("hint", "")), ""])
            text = ctk.CTkTextbox(card, height=210, font=_f(13), wrap="char", fg_color=C["card"])
            text.pack(fill="x", padx=16, pady=(0, 14))
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")
            button = btn_soft(card, text="本章已复习 ✓" if reviewed else "标记本章已复习",
                              command=lambda n=number: self._finance_mark_formula(n))
            button.pack(anchor="e", padx=16, pady=(0, 12))
            if reviewed:
                button.configure(state="disabled")

    @staticmethod
    def _finance_readable(value):
        if isinstance(value, dict):
            return "；".join(f"{key}：{FinanceUIMixin._finance_readable(item)}" for key, item in value.items())
        if isinstance(value, list):
            return "；".join(FinanceUIMixin._finance_readable(item) for item in value)
        return str(value or "")

    def _finance_mark_formula(self, number):
        def mutate(progress):
            seen = finance.state(progress["game"])["formula_seen"]
            key = f"chapter:{number}"
            if key not in seen:
                seen.append(key)
            return True
        if self._commit(mutate):
            self._show_page("town", self._build_finance_formulas)

    def _build_finance_companions(self):
        frame = self._scroll()
        self._heading(frame, "精灵伙伴与学习工具", "同时携带一位精灵，和三位主角一起经营小镇")
        for companion in finance.view(self.g)["companions"]:
            card = self._card_frame(frame)
            card.pack(fill="x", pady=6)
            image = self._finance_image(card, companion["asset"], 100)
            if image:
                image.pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(card, text=companion["name"] + " · " + companion["role"], font=_f(14, "bold"), anchor="w").pack(fill="x", padx=16, pady=(16, 5))
            ctk.CTkLabel(card, text=f"完成财管第{companion['unlock_chapter']}章开放 · 招募 {companion['price']}金币", font=_f(11), anchor="w").pack(fill="x", padx=16, pady=5)
            def act(cid=companion["id"], owned=companion["owned"]):
                if self._commit(lambda p: finance.equip_companion(p, cid) if owned else finance.recruit(p, cid)):
                    self._show_page("town", self._build_finance_companions)
            button = btn_soft(card, text="休息一下" if companion["equipped"] else "一起出发" if companion["owned"] else "招募", command=act)
            button.pack(anchor="e", padx=16, pady=(0, 12))
            if not companion["owned"] and not companion["unlocked"]:
                button.configure(state="disabled")
        for prop in finance.CONFIG["props"]:
            if prop["kind"] != "tool":
                continue
            card = self._card_frame(frame)
            card.pack(fill="x", pady=5)
            image = self._finance_image(card, prop["asset"], 85)
            if image:
                image.pack(side="left", padx=12)
            ctk.CTkLabel(card, text=prop["name"], font=_f(14, "bold")).pack(side="left", padx=16, pady=25)
            owned = prop["id"] in self.g["inventory"]
            def use(item=prop, owned=owned):
                if not owned:
                    if not self._commit(lambda p: game.buy_item(p, item["id"])):
                        return
                self._show_page("town", lambda: self._build_finance_tool(item.get("tool") or item["utility"]))
            btn_soft(card, text="打开工具" if owned else f"兑换并打开 · {prop['price']}金币", command=use).pack(side="right", padx=16)

    def _build_finance_tool(self, tool):
        if tool == "formulas":
            self._build_finance_formulas()
            return
        if tool == "review":
            self._build_finance_rescue()
            return
        frame = self._scroll()
        tools = finance.state(self.g)["tools"]
        if tool == "scratch":
            self._heading(frame, "成本算盘 · 计算草稿", "记录公式、代入与中间结果，草稿可保存续写")
            box = ctk.CTkTextbox(frame, height=430, font=_f(15), wrap="char")
            box.pack(fill="both", expand=True, pady=10)
            box.insert("1.0", tools["scratch"])
            def save():
                text = box.get("1.0", "end").strip()
                if self._commit(lambda p: finance.state(p["game"])["tools"].update(scratch=text)):
                    messagebox.showinfo("已保存", "计算草稿已保存。")
            btn_primary(frame, text="保存草稿", command=save).pack(fill="x", pady=12)
        else:
            self._heading(frame, "预算沙漏 · 专注25分钟", "一段安静的学习时间，计时暂停后可重新开始")
            label = ctk.CTkLabel(frame, text="", font=_f(48, "bold"), text_color=C["brand"])
            label.pack(pady=45)
            def tick():
                if not label.winfo_exists():
                    return
                current = finance.state(self.g)["tools"]
                start = current["focus_started_at"]
                remaining = max(0, current["focus_seconds"] - int(time.time() - start)) if start else current["focus_seconds"]
                label.configure(text=f"{remaining//60:02d}:{remaining%60:02d}" if remaining else "专注完成！")
                label.after(1000, tick)
            def start():
                self._commit(lambda p: finance.state(p["game"])["tools"].update(focus_started_at=time.time(), focus_seconds=1500))
            def stop():
                self._commit(lambda p: finance.state(p["game"])["tools"].update(focus_started_at=None, focus_seconds=1500))
            btn_primary(frame, text="开始25分钟", command=start).pack(fill="x", pady=6)
            btn_soft(frame, text="停止并重置", command=stop).pack(fill="x", pady=6)
            tick()
