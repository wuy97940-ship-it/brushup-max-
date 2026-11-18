"""离线角色资源、透明叠加层与冒险地图。原创场景直接绘制于画布。"""
from __future__ import annotations

import math
import json
import time
import tkinter as tk
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import RLock, current_thread, main_thread
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageTk, ImageOps

import game
import desktop_wardrobe as wardrobe
import desktop_suits as suits
from store import resource_path


class _BoundedCache(OrderedDict):
    """缓存只保留最近使用项；活动窗口自身持有正在显示的Tk图片。"""
    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def get(self, key, default=None):
        return self[key] if key in self else default

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        while len(self) > self.limit:
            self.popitem(last=False)


class SpriteLibrary:
    """共享PIL底图与合成缓存；Tk图片只在主线程创建。"""
    def __init__(self) -> None:
        self._source = _BoundedCache(80)
        self._composed = _BoundedCache(32)
        self._mouth_positions = _BoundedCache(32)
        self._parts = _BoundedCache(16)
        self._tk = _BoundedCache(96)
        self._ctk = _BoundedCache(96)
        self._lock = RLock()
        self._image_reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix="商品图片预读")
        manifest_path = resource_path("assets/character_manifest.json")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    def _read(self, path: Path, *, atlas=False) -> Image.Image:
        key = ("file", str(path), atlas)
        with self._lock:
            cached = self._source.get(key)
            if cached is None:
                with Image.open(path) as original:
                    cached = original.convert("RGBA")
                if not atlas and max(cached.size) > 512:
                    cached.thumbnail((512, 512), Image.Resampling.LANCZOS)
                self._source[key] = cached
            return cached

    def source(self, character: str, pose: str = "idle") -> Image.Image:
        with self._lock:
            definition = self.manifest.get("characters", {}).get(character, {})
            poses = definition.get("poses", {})
            actual_pose = wardrobe.canonical_pose(character, pose)
            actual_pose = definition.get("aliases", {}).get(actual_pose, actual_pose)
            if actual_pose not in poses:
                actual_pose = {"walk": "idle", "think": "idle", "happy": "celebrate", "chest": "celebrate"}.get(actual_pose, actual_pose)
            if actual_pose not in poses:
                actual_pose = "idle"
            key = ("character", character, actual_pose)
            cached = self._source.get(key)
            if cached is not None:
                return cached
            prepared = self.manifest.get("prepared_poses", {}).get(character, {}).get(actual_pose)
            if prepared:
                prepared_path = resource_path("assets/" + prepared)
                if prepared_path.is_file():
                    cached = self._read(prepared_path)
                    if cached.size == (512, 512):
                        self._source[key] = cached
                        return cached
            relative = poses.get(actual_pose, f"characters/{character}_{actual_pose}.png")
            path = resource_path("assets/" + relative)
            if not path.is_file():
                path = resource_path("assets/characters/xiaoyuan_idle.png")
            if character == "orange_adventurer" and definition.get("atlas"):
                frame = wardrobe.atlas_frame(self._read(path, atlas=True), actual_pose)
            elif actual_pose in definition.get("pose_frames", {}):
                atlas = self._read(path, atlas=True)
                col, row = definition["pose_frames"][actual_pose]
                columns, rows = definition["atlas_grid"]
                frame = atlas.crop((round(atlas.width*col/columns), round(atlas.height*row/rows),
                                    round(atlas.width*(col+1)/columns), round(atlas.height*(row+1)/rows)))
            else:
                frame = self._read(path)
                if path.name.endswith("_v510.png"):
                    # 补充姿态图的网格间有相邻尾尖碎片；按主体连通域裁出范围。
                    from PIL import ImageDraw, ImageChops
                    alpha = frame.getchannel("A")
                    solid = alpha.point(lambda value: 255 if value >= 32 else 0)
                    center = (frame.width//2, frame.height//2)
                    if solid.getpixel(center):
                        ImageDraw.floodfill(solid, center, 128)
                        body = solid.point(lambda value: 255 if value == 128 else 0)
                        box = body.getbbox()
                        if box:
                            mask = Image.new("L", frame.size)
                            ImageDraw.Draw(mask).rectangle((max(0, box[0]-2), max(0, box[1]-2), min(frame.width, box[2]+2), min(frame.height, box[3]+2)), fill=255)
                            frame = frame.copy()
                            frame.putalpha(ImageChops.multiply(alpha, mask))
            cached = wardrobe.normalize_frame(frame)
            self._source[key] = cached
            return cached

    @staticmethod
    def _require_main_thread():
        if current_thread() is not main_thread():
            raise RuntimeError("Tk图片须在界面主线程创建；后台预读请调用item_source或warm_items")

    def photo(self, character: str, pose: str, size: int) -> ImageTk.PhotoImage:
        self._require_main_thread()
        key = (character, pose, size)
        if key not in self._tk:
            self._tk[key] = ImageTk.PhotoImage(self.source(character, pose).resize((size, size), Image.Resampling.LANCZOS))
        return self._tk[key]

    def ctk_image(self, character: str, pose: str, size: int) -> ctk.CTkImage:
        self._require_main_thread()
        key = (character, pose, size)
        if key not in self._ctk:
            self._ctk[key] = ctk.CTkImage(self.source(character, pose), size=(size, size))
        return self._ctk[key]

    def _actor_key(self, g, pose, size=None):
        from finance import companion_ids
        suit=suits.matched(g)
        action=suits.pose_key(suit,pose) if suit else wardrobe.canonical_pose(g['skin'],pose)
        return ("actor", g["skin"], action, g.get("outfit"), g.get("headwear"),
                g.get('footwear'), g.get('pawgear'),
                *(g.get("equipment", {}).get(slot) for slot in ("xp", "coins", "wonder")),
                tuple(companion_ids(g)), size)

    def _wear_source(self, item_id):
        if not item_id:
            return None
        item = game.CATALOG.get(item_id, {})
        candidates = [resource_path(f"assets/market/wearables/{item_id}.png")]
        if item_id in self.manifest.get("overlays", {}):
            candidates.append(resource_path("assets/" + self.manifest["overlays"][item_id]))
        if item.get("fit_character") and item.get("asset"):
            candidates.append(resource_path("assets/" + item["asset"]))
        candidates.extend((resource_path(f"assets/overlays/{item_id}.png"),
                           resource_path(f"assets/shop/rendered/{item_id}_layer.png")))
        path = next((path for path in candidates if path.is_file()), None)
        return self._read(path) if path else None

    def compose(self, g, pose="idle") -> Image.Image:
        with self._lock:
            key = self._actor_key(g, pose)
            cached = self._composed.get(key)
            if cached is not None:
                self._mouth_positions.get(key)
                return cached
            role = g["skin"]
            mouths = {"xiaoyuan": ((294, 248), (390, 390)),
                      "orange_adventurer": ((274, 261), (374, 389)), "xiaobao": ((279, 190), (175, 376))}
            mouth = mouths.get(role, mouths["xiaoyuan"])[int(wardrobe.canonical_pose(role, pose) == "sleep")]
            suit=suits.matched(g)
            suit_path=resource_path('assets/'+suit['poses'][suits.pose_key(suit,pose)]) if suit else None
            base=self._read(suit_path) if suit_path and suit_path.is_file() else self.source(role,pose)
            complete_suit=bool(suit_path and suit_path.is_file())
            image = Image.new("RGBA", (512, 512))
            equipment = g.get("equipment", {})
            wonder_id = equipment.get("wonder")
            wonder = game.CATALOG.get(wonder_id, {})
            wonder_source = self._wear_source(wonder_id)
            if wonder_source is not None and wonder.get("layer") == "back":
                image.alpha_composite(wardrobe.accessory_layer(wonder_source, "wonder", role, pose, wonder_id))
            image.alpha_composite(base)
            outfit_id = g.get("outfit")
            from desktop_market import SHOP_CATALOG
            outfit = SHOP_CATALOG.get(outfit_id, game.CATALOG.get(outfit_id, {}))
            headwear = g.get("headwear")
            hat_source, hat_id = None, headwear
            outfit_source = self._wear_source(outfit_id) if not complete_suit else None
            if not complete_suit and outfit.get("fit_character") == role and outfit_source is not None:
                parts = self._parts.get(outfit_id)
                if parts is None:
                    parts = (wardrobe.cropped(outfit_source),None) if outfit.get('wearable_layout')=='garment_only' else wardrobe.garment_parts(outfit_source, outfit_id)
                    self._parts[outfit_id] = parts
                cloth, suit_hat = parts
                image.alpha_composite(wardrobe.garment_layer(base, cloth, role, pose))
                if not headwear:
                    hat_source, hat_id = suit_hat, outfit_id
            elif not complete_suit and outfit_source is not None and not outfit.get("fit_character"):
                # 兼容迁移前把六顶场景帽存于outfit的旧进度。
                headwear = headwear or outfit_id
            if headwear and not complete_suit:
                hat_source, hat_id = self._wear_source(headwear), headwear
            for slot in ("xp", "coins"):
                item_id = equipment.get(slot)
                layer = self._wear_source(item_id)
                if layer is not None:
                    image.alpha_composite(wardrobe.accessory_layer(layer, slot, role, pose, item_id))
            if wonder_source is not None and wonder.get("layer") == "front":
                image.alpha_composite(wardrobe.accessory_layer(wonder_source, "wonder", role, pose, wonder_id))
            for slot in ('footwear', 'pawgear'):
                item_id = g.get(slot)
                source = self._wear_source(item_id) if not complete_suit else None
                if source is not None and not complete_suit:
                    image.alpha_composite(wardrobe.limb_layer(source, slot, role, pose))
            from finance import companion_ids
            for index, identifier in enumerate(companion_ids(g)):
                companion = game.CATALOG.get(identifier, {})
                if companion.get("asset"):
                    path = resource_path("assets/" + companion["asset"])
                    if path.is_file():
                        small = self._read(path).copy()
                        small.thumbnail((160, 160), Image.Resampling.LANCZOS)
                        image.alpha_composite(small, (350 if index == 0 else 0, 512-small.height))
            if hat_source is not None:
                image, mouth = wardrobe.fitted_headwear(image, hat_source, role, pose, hat_id, mouth)
            self._mouth_positions[key] = mouth
            self._composed[key] = image
            return image

    def actor_mouth(self, g, pose):
        with self._lock:
            self.compose(g, pose)
            return self._mouth_positions[self._actor_key(g, pose)]

    def portrait(self, g: dict, size: int = 54, pose: str = "idle") -> ctk.CTkImage:
        self._require_main_thread()
        key = self._actor_key(g, pose, size)
        if key not in self._ctk:
            self._ctk[key] = ctk.CTkImage(self.compose(g, pose), size=(size, size))
        return self._ctk[key]

    def actor_photo(self, g, pose, size):
        self._require_main_thread()
        key = self._actor_key(g, pose, size)
        if key not in self._tk:
            self._tk[key] = ImageTk.PhotoImage(self.compose(g, pose).resize((size, size), Image.Resampling.LANCZOS))
        return self._tk[key]

    def item_source(self, item_id, *, thumbnail=False):
        """后台可调用的PIL读取，优先正式商品图；返回副本以免调用方污染共享缓存。"""
        item = game.CATALOG.get(item_id, {})
        folders = ("thumbs", "items") if thumbnail else ("items", "thumbs")
        candidates = [resource_path(f"assets/market/{folder}/{item_id}.png") for folder in folders]
        candidates.append(resource_path(f"assets/shop/rendered/{item_id}.png"))
        if item.get("asset"):
            candidates.append(resource_path("assets/" + item["asset"]))
        path = next((path for path in candidates if path.is_file()), None)
        if path:
            return self._read(path).copy()
        if item.get("character"):
            return self.source(item["character"]).copy()
        path = resource_path(f"assets/overlays/{item_id}.png")
        return self._read(path).copy() if path.is_file() else None

    def warm_items(self, item_ids):
        """仅预读PIL小图；可直接提交后台线程池，不触碰Tk。"""
        return {item_id: self.item_source(item_id, thumbnail=True) is not None for item_id in item_ids}

    def warm_items_async(self, item_ids):
        return self._image_reader.submit(self.warm_items, tuple(item_ids))

    def warm_backgrounds_async(self):
        def read():
            paths=[resource_path('assets/backgrounds') / name for name in ('forest_day_v520.png', 'island_day_v520.png', 'stars_day_v520.png', 'audit_time_day_v570.png')]
            for path in paths:
                self._read(path,atlas=True)
            return len(paths)
        return self._image_reader.submit(read)

    def close(self):
        # 解码不操作Tk；等待队列退出后，主线程才恢复自动回收及销毁根窗口。
        self._image_reader.shutdown(wait=True, cancel_futures=True)

    def item_icon(self, item_id, size=96):
        self._require_main_thread()
        key = ("item", item_id, size)
        if key not in self._ctk:
            source = self.item_source(item_id, thumbnail=size <= 192)
            if source is None:
                return None
            self._ctk[key] = ctk.CTkImage(source, size=(size, size))
        return self._ctk[key]

    market_icon = item_icon

    def cached_item_icon(self, item_id, size=96):
        """主线程只查现成显示图；未命中交给异步预读，不在切分类时读盘。"""
        self._require_main_thread()
        return self._ctk.get(("item", item_id, size))

    def market_photo(self, item_id, size=90):
        self._require_main_thread()
        key = ("item", item_id, size)
        if key not in self._tk:
            source = self.item_source(item_id, thumbnail=size <= 192)
            if source is None:
                return None
            self._tk[key] = ImageTk.PhotoImage(source.resize((size, size), Image.Resampling.LANCZOS))
        return self._tk[key]

    def item_photo_fit(self, identifier, width, height):
        self._require_main_thread()
        width, height = max(1, round(width)), max(1, round(height))
        key = ("home-item", identifier, width, height)
        if key not in self._tk:
            source = self.item_source(identifier)
            if source is None:
                return None
            bounds = source.getchannel("A").getbbox()
            source = source.crop(bounds) if bounds else source
            source.thumbnail((width, height), Image.Resampling.LANCZOS)
            self._tk[key] = ImageTk.PhotoImage(source)
        return self._tk[key]

    def room_photo(self, room, width, height):
        self._require_main_thread()
        style = "both" if room.get("wallpaper") and room.get("floor") else "wallpaper" if room.get("wallpaper") else "floor" if room.get("floor") else "base"
        width, height = max(1, round(width)), max(1, round(height))
        key = ("room", style, width, height)
        if key not in self._tk:
            path = resource_path("assets/market/rooms/" + style + ".png")
            if not path.is_file():
                return None
            source = self._read(path, atlas=True)
            self._tk[key] = ImageTk.PhotoImage(source.resize((width,height), Image.Resampling.LANCZOS))
        return self._tk[key]

    def cache_info(self):
        with self._lock:
            return {name: {"count": len(cache), "limit": cache.limit} for name, cache in
                    (("source", self._source), ("composed", self._composed), ("mouth", self._mouth_positions), ("parts", self._parts), ("tk", self._tk), ("ctk", self._ctk))}

    def effect_photo(self, item_id, size=48):
        self._require_main_thread()
        path = resource_path(f"assets/market/effects/{item_id}.png")
        if not path.is_file():
            return self.market_photo(item_id, size)
        key = ("effect", item_id, size)
        if key not in self._tk:
            self._tk[key] = ImageTk.PhotoImage(self._read(path).resize((size, size), Image.Resampling.LANCZOS))
        return self._tk[key]


class AdventureScene(ctk.CTkFrame):
    def __init__(self, master, sprites: SpriteLibrary, g: dict, *, biome: str = "forest",
                 height: int = 230, nodes: list[dict] | None = None, on_node=None,
                 boss: bool = False, pose: str = "idle", companions_snapshot: list[str] | None = None, scene_id: str | None = None, **kwargs) -> None:
        initial_biome = next(b for b in game.BIOMES if b["id"] == biome)
        kwargs.setdefault("fg_color", (initial_biome["light"], initial_biome["dark"]))
        kwargs.setdefault("border_width", 0)
        super().__init__(master, height=height, corner_radius=18, **kwargs)
        self.pack_propagate(False)
        self.sprites = sprites
        self.g = g
        self._companions_snapshot = None if companions_snapshot is None else list(companions_snapshot)
        self.biome = initial_biome
        self.scene_id = scene_id
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
        self._background_photo = None
        self._background_key = None
        self._layout_redraw_id = None
        self._node_points = []
        self._map_walk_requested = False
        self._walk_started = None
        self._walk_from = None
        self._walk_to = None
        self._victory_started = None
        self._victory_finish = None
        self._feedback_started = None
        self._feedback_correct = None
        self._reduced_motion = g.get("product", {}).get("settings", {}).get("reduced_motion", False)
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=3, pady=3)
        self.canvas.bind("<Configure>", self._request_layout_redraw)
        reduced = g.get("product", {}).get("settings", {}).get("reduced_motion", False)
        self._timer = None if reduced else self.after(60, self._animate)

    def _request_layout_redraw(self, event=None):
        # 主城多幅地图在同轮几何协商中会收到多次Configure，只按最终尺寸绘制。
        if self._layout_redraw_id is None:
            # CTk滚动条会嵌套update_idletasks；零延时事件等几何协商退出后执行。
            self._layout_redraw_id = self.after(0, self._redraw_layout)

    def _redraw_layout(self):
        self._layout_redraw_id = None
        self.redraw()

    @classmethod
    def flush_pending_layouts(cls, owner):
        """启动进入消息循环前完成最终地图绘制，首屏不留下延迟的空画布。"""
        for child in owner.winfo_children():
            if isinstance(child, cls):
                if child._layout_redraw_id is not None:
                    child.after_cancel(child._layout_redraw_id)
                    child._layout_redraw_id = None
                    child.redraw()
            else:
                cls.flush_pending_layouts(child)

    def _apply_appearance_mode(self, mode_string: str) -> None:
        super()._apply_appearance_mode(mode_string)
        if hasattr(self, "canvas"):
            self.redraw()

    def redraw(self) -> None:
        if not self.winfo_exists():
            return
        c = self.canvas
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        if w<10 or h<10:return
        dark = ctk.get_appearance_mode() == "Dark"
        bg = self.biome["dark" if dark else "light"]
        c.configure(bg=bg)
        c.delete("all")
        self._overlays.clear()
        tint = self.biome["color"]
        self._draw_landscape(c, w, h, tint, dark)
        self._draw_ambient(c,w,h,dark)
        if self.nodes is not None:
            self._draw_nodes(c, w, h)
        else:
            self._sprite_size = min(int(220 * self._get_widget_scaling()), int(h * .90),int(w*.64))
            center=w * (.24 if self.boss else .28)
            self._sprite_xy = (max(self._sprite_size/2+4,min(w-self._sprite_size/2-4,center)), h * .53)
            if self.boss and not self.victory:
                self._draw_boss(c, w * .78, h * .50, min(70 * self._get_widget_scaling(), h * .31), tint)
            elif self.victory:
                c.create_text(w * .78, h * .45, text="★  击败！", fill="#D69C24",
                              font=("Microsoft YaHei UI", int(24 * self._get_widget_scaling()), "bold"))
            elif h > 230 * self._get_widget_scaling() and w >= 570 * self._get_widget_scaling() and not getattr(self,'overview',False):
                scale = self._get_widget_scaling()
                c.create_rectangle(w*.47,h*.27,w*.90,h*.65,fill='#243852' if dark else '#EFF5FE',outline='#486482' if dark else '#D5E3F4')
                c.create_text(w * .68, h * .39, text="准备好了吗？一起去下一关！", fill="#D4E4F8" if dark else "#365E8C",
                              font=("Microsoft YaHei UI", int(16 * scale), "bold"),width=max(1,w*.43))
                c.create_text(w * .68, h * .54, text="每一题，都让旅程前进一步", fill="#9DB9D1" if dark else "#6987A0",
                              font=("Microsoft YaHei UI", int(11 * scale)),width=max(1,w*.43))
        x, y = self._sprite_xy
        from finance import companion_render_state
        actor=companion_render_state(self.g,self._companions_snapshot)
        self._sprite_image = self.sprites.actor_photo(actor, self.pose, self._sprite_size)
        c.create_image(x, y, image=self._sprite_image, tags="hero")
        if self._victory_started is not None:
            self._draw_victory_effects(c, w, h, time.monotonic() - self._victory_started)
        if self._feedback_started is not None:
            elapsed = time.monotonic() - self._feedback_started
            if elapsed < .8:
                self._draw_feedback(c, w, h, elapsed)
        if self.nodes is None:
            from world_scenes import SCENES, CONFIG, BIOME_WORLDS
            selected = SCENES.get(self.scene_id) or (CONFIG['worlds'][BIOME_WORLDS[self.biome['id']]][0] if self.biome['id'] in BIOME_WORLDS else {})
            text = "案例守护者" if self.boss else selected.get('name', self.biome['name'])
            label=c.create_text(w - 24, 22, text=text, anchor="ne", fill="#E4EDFF" if dark else "#365578",
                          font=("Microsoft YaHei UI", 11, "bold"))
            bounds=c.bbox(label)
            plate=c.create_rectangle(bounds[0]-8,bounds[1]-4,bounds[2]+8,bounds[3]+4,fill='#223755' if dark else '#EFF5FE',outline='')
            c.tag_lower(plate,label)

    def _draw_landscape(self, c, w, h, tint, dark) -> None:
        biome = self.biome["id"]
        from world_scenes import background
        path = background(getattr(self,'scene_id',None),biome,dark)
        if path.is_file():
            key=(str(path),w,h,bool(getattr(self,'overview',False)))
            if self._background_key!=key:
                # PIL解码走现有有界素材缓存，Tk照片由场景主线程持有。
                source=self.sprites._read(path,atlas=True)
                if getattr(self,'overview',False):
                    display=ImageOps.pad(source,(int(w),int(h)),method=Image.Resampling.LANCZOS,
                                         color=self.biome['dark' if dark else 'light'],centering=(.5,.5))
                else:
                    display=ImageOps.fit(source,(int(w),int(h)),method=Image.Resampling.LANCZOS,centering=(.5,.68))
                self._background_photo=ImageTk.PhotoImage(display)
                self._background_key=key
            c.create_image(0,0,image=self._background_photo,anchor='nw',tags='background')
            return
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

    def _draw_ambient(self,c,w,h,dark):
        if self._background_photo is None or self._reduced_motion:
            return
        # 只创建六个小粒子，动画移动粒子而不重画背景。
        for i in range(6):
            x,y=(i+.5)*w/6,h*(.18+.12*(i%3))
            color='#BCE3CC' if self.biome['id']=='forest' else '#BDEFFF' if self.biome['id']=='island' else '#EDD6FF'
            if self.biome['id']=='island':
                c.create_line(x-8,y,x+8,y,fill=color,width=1,tags=('ambient',f'ambient_{i}'))
            else:
                c.create_oval(x-2,y-2,x+2,y+2,fill=color,outline='',tags=('ambient',f'ambient_{i}'))

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
            c.create_rectangle(x-40*scale,y+26*scale,x+40*scale,y+49*scale,fill='#F0F5FD',outline='',tags=tag)
            c.create_text(x, y + 36 * scale, text=stars, fill="#936B1A" if node["cleared"] else "#435F80",
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
        if self._reduced_motion:
            self.set_pose("celebrate", victory=True)
            if on_reveal:
                on_reveal()
            return
        self._victory_started = time.monotonic()
        self._victory_finish = on_reveal
        self.set_pose("celebrate", victory=True)

    def _animate(self) -> None:
        if not self.winfo_exists():
            return
        if not self.winfo_viewable():
            self._timer = self.after(250, self._animate)
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
        for i,item in enumerate(self.canvas.find_withtag('ambient')):
            wave=math.sin(self._phase+i)*.22
            self.canvas.move(item,wave,.06*math.cos(self._phase+i))
        self._timer = self.after(60, self._animate)

    def set_pose(self, pose: str, *, victory: bool = False) -> None:
        previous_victory=self.victory
        self.pose = pose
        self.victory = victory or self.victory
        heroes=self.canvas.find_withtag('hero')
        if self.nodes is None and heroes and previous_victory==self.victory:
            from finance import companion_render_state
            actor=companion_render_state(self.g,self._companions_snapshot)
            self._sprite_image=self.sprites.actor_photo(actor,self.pose,self._sprite_size)
            for item in heroes:self.canvas.itemconfigure(item,image=self._sprite_image)
            if pose in ('idle','think','sleep'):
                self._feedback_started=None;self.canvas.delete('effect')
        else:self.redraw()

    def pulse(self, pose: str) -> None:
        if self._pulse_timer:
            self.after_cancel(self._pulse_timer)
        self.set_pose(pose)
        if not self._reduced_motion and pose in ("attack", "happy", "hurt", "smile", "wink", "wave", "proud", "celebrate", "sad", "cry", "surprise", "think"):
            self._feedback_started = time.monotonic()
            self._feedback_correct = pose in ("attack", "happy", "smile", "wink", "wave", "proud", "celebrate")
        # 新版表情保持到下一题；不因重建题目控件稍慢而提前消失。
        self._pulse_timer = None if self.g.get("product") else self.after(950, lambda: self.set_pose("idle"))

    def destroy(self) -> None:
        for timer in (self._timer, self._pulse_timer, self._layout_redraw_id):
            if timer:
                try:
                    self.after_cancel(timer)
                except tk.TclError:
                    pass
        super().destroy()
