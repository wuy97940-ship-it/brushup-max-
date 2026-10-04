"""离线角色资源、透明叠加层与冒险地图。原创场景直接绘制于画布。"""
from __future__ import annotations

import math
import json
import time
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageTk

import game
from store import resource_path


class SpriteLibrary:
    def __init__(self) -> None:
        self._source: dict[str, Image.Image] = {}
        self._tk: dict[tuple, ImageTk.PhotoImage] = {}
        self._ctk: dict[tuple, ctk.CTkImage] = {}
        manifest_path = resource_path("assets/character_manifest.json")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    def source(self, character: str, pose: str = "idle") -> Image.Image:
        aliases = {"walk": "idle", "think": "idle", "happy": "celebrate", "chest": "celebrate"}
        manifest_pose = self.manifest.get("characters", {}).get(character, {}).get("poses", {}).get(pose)
        path = resource_path("assets/" + manifest_pose) if manifest_pose else resource_path(f"assets/characters/{character}_{pose}.png")
        if not path.exists():
            path = resource_path(f"assets/characters/{character}_{aliases.get(pose, 'idle')}.png")
        if not path.exists():
            path = resource_path("assets/characters/xiaoyuan_idle.png")
        key = str(path)
        if key not in self._source:
            with Image.open(path) as original:
                image = original.convert("RGBA")
            # 游戏渲染时统一占用区域与落脚点，原始生图文件不改动。
            alpha_box = image.getchannel("A").point(lambda opacity: 255 if opacity >= 16 else 0).getbbox()
            if alpha_box:
                image = image.crop(alpha_box)
            frame = Image.new("RGBA", (512, 512))
            image.thumbnail((440, 450), Image.Resampling.LANCZOS)
            frame.alpha_composite(image, ((512 - image.width) // 2, 472 - image.height))
            self._source[key] = frame
        return self._source[key]

    def photo(self, character: str, pose: str, size: int) -> ImageTk.PhotoImage:
        key = (character, pose, size)
        if key not in self._tk:
            self._tk[key] = ImageTk.PhotoImage(self.source(character, pose).resize((size, size), Image.Resampling.LANCZOS))
        return self._tk[key]

    def ctk_image(self, character: str, pose: str, size: int) -> ctk.CTkImage:
        key = (character, pose, size)
        if key not in self._ctk:
            self._ctk[key] = ctk.CTkImage(self.source(character, pose), size=(size, size))
        return self._ctk[key]

    def _actor_key(self, g, pose, size):
        return ("actor", g["skin"], pose, g.get("outfit"),
                *(g.get("equipment", {}).get(slot) for slot in ("xp", "coins", "wonder")),
                g.get("finance_expansion", {}).get("companion"), size)

    def compose(self, g, pose="idle") -> Image.Image:
        image = Image.new("RGBA", (512, 512))
        wonder_id = g.get("equipment", {}).get("wonder")
        wonder = game.CATALOG.get(wonder_id, {})

        def overlay(relative):
            path = resource_path(relative)
            if path.is_file():
                key = str(path)
                if key not in self._source:
                    with Image.open(path) as original:
                        self._source[key] = original.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
                image.alpha_composite(self._source[key])

        if wonder.get("layer") == "back":
            overlay(f"assets/shop/rendered/{wonder_id}_layer.png")
        image.alpha_composite(self.source(g["skin"], pose))
        for name in (g.get("outfit"), g.get("equipment", {}).get("xp"), g.get("equipment", {}).get("coins")):
            if name:
                item = game.CATALOG.get(name, {})
                overlay("assets/" + item["asset"] if item.get("fit_character") and item.get("asset") else f"assets/overlays/{name}.png")
        if wonder.get("layer") == "front":
            overlay(f"assets/shop/rendered/{wonder_id}_layer.png")
        companion = game.CATALOG.get(g.get("finance_expansion", {}).get("companion"), {})
        if companion.get("asset"):
            path = resource_path("assets/" + companion["asset"])
            if path.is_file():
                with Image.open(path) as source:
                    small = source.convert("RGBA")
                small.thumbnail((160, 160), Image.Resampling.LANCZOS)
                image.alpha_composite(small, (350, 512-small.height))
        return image

    def portrait(self, g: dict, size: int = 54, pose: str = "idle") -> ctk.CTkImage:
        key = self._actor_key(g, pose, size)
        if key not in self._ctk:
            self._ctk[key] = ctk.CTkImage(self.compose(g, pose), size=(size, size))
        return self._ctk[key]

    def actor_photo(self, g, pose, size):
        key = self._actor_key(g, pose, size)
        if key not in self._tk:
            self._tk[key] = ImageTk.PhotoImage(self.compose(g, pose).resize((size, size), Image.Resampling.LANCZOS))
        return self._tk[key]

    def item_icon(self, item_id, size=96):
        path = resource_path(f"assets/shop/rendered/{item_id}.png")
        item = game.CATALOG.get(item_id, {})
        if item.get("asset"):
            path = resource_path("assets/" + item["asset"])
        elif item.get("character"):
            path = resource_path(f"assets/characters/{item['character']}_idle.png")
        if not path.is_file():
            return None
        key = ("item", item_id, size)
        if key not in self._ctk:
            with Image.open(path) as original:
                self._ctk[key] = ctk.CTkImage(original.convert("RGBA"), size=(size, size))
        return self._ctk[key]


class AdventureScene(ctk.CTkFrame):
    def __init__(self, master, sprites: SpriteLibrary, g: dict, *, biome: str = "forest",
                 height: int = 230, nodes: list[dict] | None = None, on_node=None,
                 boss: bool = False, pose: str = "idle", **kwargs) -> None:
        initial_biome = next(b for b in game.BIOMES if b["id"] == biome)
        kwargs.setdefault("fg_color", (initial_biome["light"], initial_biome["dark"]))
        kwargs.setdefault("border_width", 0)
        super().__init__(master, height=height, corner_radius=18, **kwargs)
        self.pack_propagate(False)
        self.sprites = sprites
        self.g = g
        self.biome = initial_biome
        self.nodes = nodes
        self.on_node = on_node
        self.boss = boss
        self.pose = pose
        self.victory = False
        self._phase = 0.0
        self._timer = None
        self._pulse_timer = None
        self._sprite_xy = (0, 0)
        self._sprite_size = 160
        self._sprite_image = None
        self._overlays: list[ImageTk.PhotoImage] = []
        self._node_points = []
        self._map_walk_requested = False
        self._walk_started = None
        self._walk_from = None
        self._walk_to = None
        self._victory_started = None
        self._victory_finish = None
        self._feedback_started = None
        self._feedback_correct = None
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=3, pady=3)
        self.canvas.bind("<Configure>", lambda event: self.redraw())
        self._timer = self.after(60, self._animate)

    def _apply_appearance_mode(self, mode_string: str) -> None:
        super()._apply_appearance_mode(mode_string)
        if hasattr(self, "canvas"):
            self.redraw()

    def redraw(self) -> None:
        if not self.winfo_exists():
            return
        c = self.canvas
        w = max(300, c.winfo_width())
        h = max(120, c.winfo_height())
        dark = ctk.get_appearance_mode() == "Dark"
        bg = self.biome["dark" if dark else "light"]
        c.configure(bg=bg)
        c.delete("all")
        self._overlays.clear()
        tint = self.biome["color"]
        self._draw_landscape(c, w, h, tint, dark)
        if self.nodes is not None:
            self._draw_nodes(c, w, h)
        else:
            self._sprite_size = min(int(220 * self._get_widget_scaling()), int(h * .90))
            self._sprite_xy = (w * (.24 if self.boss else .28), h * .53)
            if self.boss and not self.victory:
                self._draw_boss(c, w * .78, h * .50, min(70 * self._get_widget_scaling(), h * .31), tint)
            elif self.victory:
                c.create_text(w * .78, h * .45, text="★  击败！", fill="#D69C24",
                              font=("Microsoft YaHei UI", int(24 * self._get_widget_scaling()), "bold"))
            elif h > 230:
                scale = self._get_widget_scaling()
                c.create_text(w * .68, h * .39, text="准备好了吗？一起去下一关！", fill="#D4E4F8" if dark else "#365E8C",
                              font=("Microsoft YaHei UI", int(16 * scale), "bold"))
                c.create_text(w * .68, h * .54, text="每一题，都让旅程前进一步", fill="#9DB9D1" if dark else "#6987A0",
                              font=("Microsoft YaHei UI", int(11 * scale)))
        x, y = self._sprite_xy
        self._sprite_image = self.sprites.actor_photo(self.g, self.pose, self._sprite_size)
        c.create_image(x, y, image=self._sprite_image, tags="hero")
        if self._victory_started is not None:
            self._draw_victory_effects(c, w, h, time.monotonic() - self._victory_started)
        if self._feedback_started is not None:
            elapsed = time.monotonic() - self._feedback_started
            if elapsed < .8:
                self._draw_feedback(c, w, h, elapsed)
        if self.nodes is None:
            text = "案例守护者" if self.boss else self.biome["name"]
            c.create_text(w - 24, 22, text=text, anchor="ne", fill="#C8D7F3" if dark else "#506886",
                          font=("Microsoft YaHei UI", 11, "bold"))

    def _draw_landscape(self, c, w, h, tint, dark) -> None:
        biome = self.biome["id"]
        cloud = "#324159" if dark else "#FFFFFF"
        for x, y in ((w * .1, h * .16), (w * .58, h * .10), (w * .86, h * .24)):
            c.create_oval(x - 42, y - 10, x + 42, y + 14, fill=cloud, outline="")
            c.create_oval(x - 23, y - 23, x + 23, y + 10, fill=cloud, outline="")
        ground = "#243C37" if dark else "#C7E8D8"
        if biome == "forest":
            c.create_oval(-w * .1, h * .72, w * .65, h * 1.7, fill=ground, outline="")
            c.create_oval(w * .35, h * .64, w * 1.25, h * 1.7, fill="#31554A" if dark else "#B9DDCA", outline="")
            for x in (w * .08, w * .54, w * .91):
                c.create_rectangle(x - 5, h * .45, x + 5, h * .9, fill="#7F9C85", outline="")
                c.create_oval(x - 42, h * .35, x + 42, h * .68, fill="#376657" if dark else "#8BC7A8", outline="")
        elif biome == "island":
            c.create_rectangle(0, h * .67, w, h, fill="#214B62" if dark else "#A5DEF2", outline="")
            c.create_oval(-50, h * .77, w * .55, h * 1.35, fill="#70694F" if dark else "#F1DFB7", outline="")
            for x in (w * .35, w * .7, w * .87):
                c.create_line(x, h * .78, x + 25, h * .50, fill=cloud, width=3, smooth=True)
        elif biome == "snow":
            for x, size in ((w * .20, .62), (w * .55, .82), (w * .85, .58)):
                c.create_polygon(x - h * .35, h, x, h * (1 - size), x + h * .38, h,
                                 fill="#435576" if dark else "#C4D8EF", outline="")
                c.create_polygon(x - h * .10, h * (1 - size + .2), x, h * (1 - size),
                                 x + h * .1, h * (1 - size + .2), fill=cloud, outline="")
        elif biome == "ruins":
            c.create_rectangle(0, h * .83, w, h, fill="#514332" if dark else "#E5D5B3", outline="")
            for x in (w * .1, w * .53, w * .90):
                c.create_rectangle(x - 13, h * .37, x + 13, h * .85,
                                   fill="#79684A" if dark else "#D5BD8E", outline="")
                c.create_rectangle(x - 21, h * .35, x + 21, h * .41, fill=tint, outline="")
        elif biome == "sky":
            for x in (w * .11, w * .54, w * .85):
                c.create_oval(x - 74, h * .80, x + 74, h * 1.05, fill=cloud, outline="")
                c.create_rectangle(x - 27, h * .42, x + 27, h * .86, fill="#5E5C86" if dark else "#C9CBF3", outline="")
                c.create_polygon(x - 36, h * .43, x, h * .24, x + 36, h * .43, fill=tint, outline="")
        else:
            for index in range(30):
                x = (index * 97 + 21) % w
                y = (index * 59 + 15) % h
                c.create_oval(x, y, x + 3, y + 3, fill="#DED5FF", outline="")
            c.create_oval(w * .7, h * .12, w * .7 + 50, h * .12 + 50,
                          fill="#B5A3ED", outline="")
            c.create_arc(w * .67, h * .11, w * .78 + 50, h * .12 + 53,
                         start=190, extent=165, style="arc", outline="#C5C7EF", width=3)

    def _draw_nodes(self, c, w, h) -> None:
        count = len(self.nodes)
        cols = 4
        scale = self._get_widget_scaling()
        spacing = (w - 140 * scale) / (cols - 1)
        points = []
        for index in range(count):
            row, col = divmod(index, cols)
            if row % 2:
                col = cols - 1 - col
            points.append((70 * scale + col * spacing, (68 + row * 105) * scale))
        for a, b in zip(points, points[1:]):
            c.create_line(*a, *b, fill="#9CB4D1", width=5, dash=(7, 5), capstyle="round")
        current = next((i for i, node in enumerate(self.nodes) if node["available"] and not node["cleared"]), count - 1)
        self._node_points = points
        for i, (node, (x, y)) in enumerate(zip(self.nodes, points)):
            tag = "stage_" + str(i)
            color = self.biome["color"] if node["cleared"] else "#3B82F6" if node["available"] else "#9BAAC0"
            boss = node["kind"] == "boss"
            radius = 25 * scale
            c.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="#FFFFFF", width=3, tags=tag)
            c.create_text(x, y, text="B" if boss else str(i + 1), fill="white",
                          font=("Microsoft YaHei UI", int(16 * scale), "bold"), tags=tag)
            stars = "★" * node["stars"] + "☆" * (3 - node["stars"]) if node["cleared"] else "Boss" if boss else "待挑战" if node["available"] else "未解锁"
            c.create_text(x, y + 36 * scale, text=stars, fill="#B58923" if node["cleared"] else "#627895",
                          font=("Microsoft YaHei UI", int(10 * scale)), tags=tag)
            if node["available"]:
                c.tag_bind(tag, "<Button-1>", lambda event, sid=node["id"]: self.on_node(sid))
                c.tag_bind(tag, "<Enter>", lambda event: c.configure(cursor="hand2"))
                c.tag_bind(tag, "<Leave>", lambda event: c.configure(cursor=""))
        self._sprite_size = int(72 * scale)
        self._sprite_xy = (points[current][0], points[current][1] - 45 * scale)
        if self._map_walk_requested:
            self._map_walk_requested = False
            self._walk_started = time.monotonic()
            self._walk_from = (points[max(0, current - 1)][0], points[max(0, current - 1)][1] - 45 * scale)
            self._walk_to = self._sprite_xy
            self.pose = "walk"

    def walk_to_current(self) -> None:
        self._map_walk_requested = True
        self.redraw()

    def _draw_boss(self, c, x, y, size, tint) -> None:
        c.create_oval(x - size * .95, y - size, x + size * .95, y + size,
                      fill="#354B75", outline="#718BC0", width=3, tags="boss")
        c.create_polygon(x - size * .7, y - size * .7, x - size * .65, y - size * 1.30,
                          x - size * .28, y - size * .85, fill="#354B75", outline="#718BC0", tags="boss")
        c.create_polygon(x + size * .7, y - size * .7, x + size * .65, y - size * 1.30,
                          x + size * .28, y - size * .85, fill="#354B75", outline="#718BC0", tags="boss")
        for dx in (-.34, .34):
            c.create_oval(x + size * dx - 9, y - 15, x + size * dx + 9, y + 3,
                          fill="#FCDB7C", outline="", tags="boss")
        c.create_arc(x - 16, y + 5, x + 16, y + 24, start=0, extent=180, style="arc",
                     outline="#CAD8F4", width=2, tags="boss")
        c.create_text(x, y + size + 15, text="知识守护者", fill=tint,
                      font=("Microsoft YaHei UI", 10, "bold"), tags="boss")

    def _draw_overlays(self, c, x, y, size) -> None:
        names = []
        if self.g.get("outfit"):
            names.append(self.g["outfit"])
        names += [item for item in self.g.get("equipment", {}).values() if item]
        for name in names:
            path = resource_path("assets/overlays/" + name + ".png")
            if path.exists():
                with Image.open(path) as raw:
                    layer = raw.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(layer)
                self._overlays.append(photo)
                c.create_image(x, y, image=photo, tags="hero")

    def _draw_feedback(self, c, w, h, elapsed) -> None:
        scale = self._get_widget_scaling()
        color = "#E1B63F" if self._feedback_correct else "#D58587"
        text = "答对了！" if self._feedback_correct else "再想想，下次一定行"
        x = w * (.78 if self.boss and self._feedback_correct else .55)
        y = h * .27 - elapsed * 25
        c.create_text(x, y, text=text, fill=color, font=("Microsoft YaHei UI", int(13 * scale), "bold"), tags="effect")
        for index in range(7):
            angle = index * math.tau / 7
            radius = 20 + elapsed * 60
            dx, dy = math.cos(angle) * radius, math.sin(angle) * radius
            c.create_oval(x + dx - 3, y + dy - 3, x + dx + 3, y + dy + 3, fill=color, outline="", tags="effect")

    def _draw_victory_effects(self, c, w, h, elapsed) -> None:
        scale = self._get_widget_scaling()
        x, y = w * .70, h * .65
        size = 39 * scale
        opened = max(0.0, min(1.0, (elapsed - .65) / .65))
        c.create_rectangle(x - size, y - size * .48, x + size, y + size * .48,
                           fill="#B77A39", outline="#FFE7A2", width=3, tags="effect")
        lift = opened * size * .85
        c.create_polygon(x - size, y - size * .48 - lift, x + size, y - size * .48 - lift,
                         x + size * .88, y - size * .86 - lift, x - size * .88, y - size * .86 - lift,
                         fill="#DCA957", outline="#FFE7A2", width=3, tags="effect")
        c.create_rectangle(x - size * .13, y - size * .1, x + size * .13, y + size * .17,
                           fill="#FEE494", outline="", tags="effect")
        if opened:
            c.create_text(x, y - size - lift - 7, text="✦   ★   ✦", fill="#EABF4C",
                           font=("Microsoft YaHei UI", int(20 * scale), "bold"), tags="effect")
        label = "守护者退场……" if elapsed < .65 else "宝箱开启……" if elapsed < 1.4 else "奖励已揭晓 · 下一关点亮"
        c.create_text(w * .70, 48 * scale, text=label, fill="#CEA039",
                       font=("Microsoft YaHei UI", int(14 * scale), "bold"), tags="effect")
        if elapsed >= 1.4:
            for index in range(15):
                dx = math.sin(index * 2.4 + elapsed) * w * .21
                dy = ((index * 23 + elapsed * 43) % max(80, h * .60))
                c.create_text(x + dx, h * .16 + dy, text="✦", fill="#D4AD3D",
                               font=("Microsoft YaHei UI", 12), tags="effect")

    def play_victory(self, on_reveal=None) -> None:
        self._victory_started = time.monotonic()
        self._victory_finish = on_reveal
        self.set_pose("celebrate", victory=True)

    def _animate(self) -> None:
        if not self.winfo_exists():
            return
        self._phase += .16
        flying = self.g.get("equipment", {}).get("wonder") in ("wonder_broom", "wonder_wings")
        offset = math.sin(self._phase) * (6 if flying else 1.5 if self.nodes else 3)
        x, y = self._sprite_xy
        if self._walk_started is not None:
            progress = min(1.0, (time.monotonic() - self._walk_started) / 1.05)
            x = self._walk_from[0] + (self._walk_to[0] - self._walk_from[0]) * progress
            y = self._walk_from[1] + (self._walk_to[1] - self._walk_from[1]) * progress
            if progress >= 1.0:
                self._walk_started = None
                self.set_pose("idle")
        elapsed = time.monotonic() - self._victory_started if self._victory_started else None
        if elapsed is not None:
            self.canvas.delete("effect")
            self._draw_victory_effects(self.canvas, self.canvas.winfo_width(), self.canvas.winfo_height(), elapsed)
            if elapsed >= .65 and self.pose != "chest":
                self.set_pose("chest", victory=True)
            if elapsed >= 1.4 and self._victory_finish is not None:
                callback, self._victory_finish = self._victory_finish, None
                callback()
            if elapsed >= 2.6:
                self._victory_started = None
                self.canvas.delete("effect")
                self.set_pose("celebrate", victory=True)
        elif self._feedback_started is not None:
            feedback_time = time.monotonic() - self._feedback_started
            self.canvas.delete("effect")
            if feedback_time < .8:
                self._draw_feedback(self.canvas, self.canvas.winfo_width(), self.canvas.winfo_height(), feedback_time)
            else:
                self._feedback_started = None
        for item in self.canvas.find_withtag("hero"):
            self.canvas.coords(item, x, y + offset)
        self._timer = self.after(60, self._animate)

    def set_pose(self, pose: str, *, victory: bool = False) -> None:
        self.pose = pose
        self.victory = victory or self.victory
        self.redraw()

    def pulse(self, pose: str) -> None:
        if self._pulse_timer:
            self.after_cancel(self._pulse_timer)
        self.set_pose(pose)
        if pose in ("attack", "happy", "hurt"):
            self._feedback_started = time.monotonic()
            self._feedback_correct = pose != "hurt"
        self._pulse_timer = self.after(950, lambda: self.set_pose("idle"))

    def destroy(self) -> None:
        for timer in (self._timer, self._pulse_timer):
            if timer:
                try:
                    self.after_cancel(timer)
                except tk.TclError:
                    pass
        super().destroy()
