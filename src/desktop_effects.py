"""商品使用演出：所有状态已落盘，只负责有图演出与保留结果。"""
from __future__ import annotations

import math
import time
import tkinter as tk

import customtkinter as ctk
import desktop_product as product
from app import C, _f, btn_ghost, btn_primary
from desktop_window_resources import ManagedWindow


class ConsumptionEffect(ManagedWindow):
    """约1.5秒非阻塞演出；关闭与跳过取消本窗口全部回调。"""

    DURATION = 1.5

    def __init__(self, app, item, hero_id, result, *, reduced_motion=False):
        super().__init__(app)
        self.app, self.item, self.result = app, item, result
        self.hero_id = hero_id
        self._timer = None
        self._closed = False
        self.completed = False
        self.frame_count = 0
        self.title(item["name"] + " · 已保存")
        self.geometry("570x560")
        self.minsize(520, 530)
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._images = []
        self.g = product.hero_preview(app.g, hero_id)
        self._poses = {}
        for pose in ("sleep", "sad", "idle", "happy", "celebrate"):
            self._poses[pose] = app.sprites.actor_photo(self.g, pose, 245)
        self._food = app.sprites.market_photo(item["id"], 95)
        self._small_food = app.sprites.market_photo(item["id"], 48)
        self._pill = app.sprites.effect_photo("revival_pill", 48)
        self._cookie = app.sprites.market_photo("food_cookie", 48)
        self._images.extend([self._food, self._small_food, self._pill, self._cookie, *self._poses.values()])
        ctk.CTkLabel(self, text=product.HEROES[hero_id]["name"] + " · " + item["name"],
                     font=_f(21, "bold"), text_color=C["brand"]).pack(pady=(17, 4))
        self.phase_label = ctk.CTkLabel(self, text="", font=_f(13))
        self.phase_label.pack(pady=3)
        self.canvas = tk.Canvas(self, width=530, height=290, bg="#F2F6FF", highlightthickness=0)
        self.canvas.pack(padx=18, fill="x")
        self.result_card = ctk.CTkFrame(self, corner_radius=15)
        self.result_card.pack(fill="x", padx=20, pady=12)
        self.result_label = ctk.CTkLabel(self.result_card, text="结果已保存，伙伴正在享用…", justify="left",
                                        font=_f(13), wraplength=475)
        self.result_label.pack(padx=17, pady=15)
        self.skip_button = btn_ghost(self, text="跳过动画，查看结果", command=self.finish)
        self.skip_button.pack(pady=3)
        self.done_button = btn_primary(self, text="知道了", command=self.destroy)
        self._started_at = time.perf_counter()
        if reduced_motion:
            self.finish()
        else:
            self._tick()

    def _kind(self):
        if self.item.get('mood_action'):
            return self.item['mood_action']
        if self.item.get('kind') == 'mana':
            return 'mana'
        identifier = self.item["id"]
        for value in ("revival", "calm", "cookie", "bento", "feast", "supply"):
            if value in identifier or self.item.get("kind") == value:
                return value
        return "cookie"

    def _draw(self, progress):
        canvas = self.canvas
        canvas.delete("all")
        kind = self._kind()
        width = max(530, self.canvas.winfo_width())
        center = width / 2
        actor_y = 166
        pose = "idle"
        phase = "准备享用"
        # 喂丹须先到达嘴边并停留，再消失与苏醒；不能在接近途中就删除道具。
        t = min(1, max(0, (progress - .15) / (.24 if kind == "revival" else .48)))
        ease = t * t * (3 - 2 * t)
        food = self._food
        if kind == "revival":
            food = self._pill
            pose = "sleep" if progress < .58 else "happy" if progress < .82 else "celebrate"
            phase = "安静休眠" if progress < .18 else "喂下还魂丹" if progress < .48 else "柔和的光在苏醒" if progress < .72 else "睁开眼睛，恢复体力"
            actor_y = 179 - 17 * max(0, min(1, (progress - .65) / .2))
            if .38 < progress < .94:
                radius = 88 + 36 * math.sin((progress - .38) / .56 * math.pi)
                for offset, color in ((16, "#EDF7D9"), (7, "#E0F0B3"), (0, "#D2E99B")):
                    canvas.create_oval(center-radius-offset, actor_y-radius-offset, center+radius+offset, actor_y+radius+offset, fill=color, outline="")
        elif kind == "calm":
            pose = "sad" if progress < .4 else "idle" if progress < .76 else "happy"
            phase = "有一点低落" if progress < .18 else "慢慢喝一口暖心饮" if progress < .7 else "心情慢慢平静下来"
        elif kind == 'mana':
            phase = '拿起蓝色魔法药' if progress < .22 else '喝下魔法药，蓝光慢慢亮起' if progress < .7 else '魔法恢复，准备施法'
            if .35 < progress < .94:
                radius = 82 + 24 * math.sin((progress - .35) / .59 * math.pi)
                for offset, color in ((15, '#E5F5FF'), (7, '#CCE9FF'), (0, '#AFDCFC')):
                    canvas.create_oval(center-radius-offset, actor_y-radius-offset,
                                       center+radius+offset, actor_y+radius+offset,
                                       fill=color, outline='', tags=('mana_glow',))
        elif kind == "bento":
            phase = "打开便当盒" if progress < .32 else "吃一口暖暖的便当" if progress < .77 else "好吃，恢复精神！"
            canvas.create_image(center+156, 225, image=self._food)
            food = None
        elif kind == "supply":
            phase = "打开补给箱" if progress < .28 else "取出食物，一起补充能量" if progress < .75 else "补给完成，又能出发了！"
            canvas.create_image(center+156, 230, image=self._food)
            food = self._cookie if progress > .27 else None
        elif kind == "feast":
            phase = "摆好丰盛餐盘" if progress < .28 else "开心享用大餐" if progress < .76 else "饱饱的，庆祝一下！"
            canvas.create_image(center+156, 225, image=self._food)
            food = None
        else:
            phase = "拿起小饼干" if progress < .22 else "靠近嘴巴，咬一小口" if progress < .7 else "吃完啦，露出笑容"
        if kind not in ("calm", "revival"):
            pose = "idle" if progress < .48 else "happy" if progress < .8 else "celebrate"
        # 坐标来自归一化512角色图；猫和企鹅嘴部高度不同，睡姿方向也不同。
        anchor = self.app.sprites.actor_mouth(self.g, pose)
        mouth = (center + (anchor[0]-256)*245/512, actor_y + (anchor[1]-256)*245/512)
        food_x = center + 156 + (mouth[0]-center-156)*ease
        food_y = 225 + (mouth[1]-225)*ease
        canvas.create_oval(center-81, 261, center+82, 277, fill="#DFE9F4", outline="")
        if kind == 'outing':
            # 出游券是行程演出，不把票券移动到伙伴嘴边。
            canvas.create_image(center, 100, image=self._food)
            canvas.create_image(center, 191, image=self._poses['happy' if progress < .8 else 'celebrate'])
            self.phase_label.configure(text='出发逛一逛，看看新风景' if progress < .75 else '愉快的行程结束，心情恢复了')
            return
        if kind == 'toy':
            canvas.create_image(center, actor_y, image=self._poses['happy' if progress < .8 else 'celebrate'])
            canvas.create_image(center+145, 205+math.sin(progress*18)*10, image=self._food)
            self.phase_label.configure(text='玩一会儿喜欢的玩具' if progress < .75 else '玩得开心，心情恢复了')
            return
        canvas.create_image(center, actor_y, image=self._poses[pose])
        if kind == "revival" and progress < .45:
            canvas.create_text(center-78, 67, text="Z z z", fill="#859DBA", font=("Microsoft YaHei UI", 16, "bold"))
        if kind in ("bento", "feast") and .3 < progress < .82:
            canvas.create_line(food_x+5, food_y+4, food_x+34, food_y+17, fill="#92A9BD", width=5)
            canvas.create_oval(food_x-15, food_y-8, food_x+14, food_y+9, fill="#FDF4DB", outline="#D6C7A6")
        if food and progress < (.55 if kind == "revival" else .82):
            canvas.create_image(food_x, food_y + math.sin(progress*27)*3 if .48 < progress < .72 else food_y, image=food)
            if kind == "cookie" and .57 < progress < .73:
                for index in range(4):
                    x = mouth[0] + math.sin(index*2)*20
                    y = mouth[1] + 25 + index*5 + (progress-.57)*90
                    canvas.create_oval(x, y, x+4, y+4, fill="#C68B43", outline="")
        if progress > .76:
            for index in range(8):
                angle = index * math.pi/4
                distance = 95 + (progress-.76)*100
                x = center + math.cos(angle)*distance
                y = 149 + math.sin(angle)*distance*.65
                canvas.create_text(x, y, text="✦", fill='#348AD4' if kind == 'mana' else "#D7A541", font=("Microsoft YaHei UI", 13))
        self.phase_label.configure(text=phase)

    def _tick(self):
        self._timer = None
        if self._closed or self.completed:
            return
        progress = min(1, (time.perf_counter() - self._started_at) / self.DURATION)
        self.frame_count += 1
        self._draw(progress)
        if progress >= 1:
            self.finish()
        else:
            self._timer = self.after(33, self._tick)

    def finish(self):
        if self._closed:
            return
        self._cancel()
        self.completed = True
        self._draw(1)
        result = self.result
        if result.get('resource') == 'mood':
            text = f"情绪 {result.get('before', 0):g} → {result.get('after', 0):g}\n实际恢复 {result.get('gain', 0):g} 点 · 体力与魔法保持原值"
        else:
            resource = '魔法' if result.get('resource') == 'mana' else '体力'
            text = f"{resource} {result.get('before', 0):g} → {result.get('after', 0):g}\n实际恢复 {result.get('gain', 0):g} 点"
            if result.get("overflow"):
                text += f" · 超出上限 {result['overflow']:g} 点"
        self.result_label.configure(text=text + "\n使用与效果已保存；关闭窗口不会重复消耗。")
        self.skip_button.pack_forget()
        self.done_button.pack(pady=(3, 12))

    def _cancel(self):
        if self._timer:
            try:
                self.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        self._cancel()
        super().destroy()
