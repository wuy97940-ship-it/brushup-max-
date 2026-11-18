"""家园场景：沿用项目画布绘制方式，家具按真实槽位和格子呈现。"""
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk
import desktop_product as product


class HomeScene(ctk.CTkFrame):
    def __init__(self, master, sprites, g: dict, *, on_select=None, height=400, compact=False):
        super().__init__(master, height=height, corner_radius=18, fg_color=("#EEF4FA", "#172536"))
        self.pack_propagate(False)
        self.sprites, self.g, self.on_select = sprites, g, on_select
        self.compact = compact
        self.preview = None
        self._actor = None
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda event: self.redraw())
        self.canvas.bind("<Button-1>", self._click)

    def _geometry(self):
        w = max(180 if self.compact else 550, self.canvas.winfo_width())
        h = max(120 if self.compact else 300, self.canvas.winfo_height())
        # 正式房间底图的踢脚线在画面60%处，物品落脚点与底图地面对应。
        top = round(18+(h-30)*.60)
        return w, h, 30, top, (w - 60) / product.CONFIG["room"]["columns"], (h - top - 24) / product.CONFIG["room"]["rows"]

    def _click(self, event):
        if not self.on_select:
            return
        w, _, left, top, cw, ch = self._geometry()
        if event.y < top:
            slot = min(product.CONFIG["room"]["wall_slots"], key=lambda key: abs(event.x - w * {"left": .33, "center": .56, "right": .79}[key]))
            self.on_select({"slot": slot})
        else:
            x, y = int((event.x - left) // cw), int((event.y - top) // ch)
            self.on_select({"x": x, "y": y})

    def set_preview(self, item: str | None, location=None, *, valid=True):
        self.preview = {"item": item, "location": location or {}, "valid": valid} if item else None
        self.redraw()

    def _round(self, x, y, x2, y2, color, radius=8, **kwargs):
        r = min(radius, (x2 - x) / 2, (y2 - y) / 2)
        points = [x+r,y,x2-r,y,x2,y,x2,y+r,x2,y2-r,x2,y2,x2-r,y2,x+r,y2,x,y2,x,y2-r,x,y+r,x,y]
        return self.canvas.create_polygon(points, smooth=True, fill=color, outline=color, **kwargs)

    def redraw(self):
        if not self.winfo_exists():
            return
        c = self.canvas
        w, h, left, top, cw, ch = self._geometry()
        dark = ctk.get_appearance_mode() == "Dark"
        room = product.state(self.g)["room"]
        if self.preview and self.preview["valid"]:
            item = product.CATALOG[self.preview["item"]]
            if item["kind"] in ("wallpaper", "floor"):
                room = {**room, item["kind"]: item["id"]}
        c.configure(bg="#172536" if dark else "#EEF4FA")
        c.delete("all")
        self._room_images = []
        background = self.sprites.room_photo(room, w-40, h-30)
        wall = "#2A455A" if dark else "#DCEBF7" if room["wallpaper"] else "#F5F0E8"
        floor = "#5B4638" if dark else "#D5AF87" if room["floor"] else "#E5D8C4"
        if background:
            self._room_images.append(background)
            c.create_image(20,18,image=background,anchor="nw")
        else:
            self._round(20, 18, w-20, h-12, wall, 16)
            c.create_rectangle(22, top, w-22, h-15, fill=floor, outline="")
            c.create_rectangle(22, top-7, w-22, top+1, fill="#93AEC5" if dark else "#CCBFAE", outline="")
        # 房间原有门，家具从空房间开始。
        if not background:
            self._round(54, 53, 113, top-8, "#6B5E50" if dark else "#C7AC8E", 6)
            self._round(61, 62, 105, top-15, "#8E7862" if dark else "#DECAAF", 4)
            c.create_oval(94, 106, 99, 111, fill="#BE9A56", outline="")
        if room["floor"] and not background:
            for y in range(int(top), int(h-15), 18):
                c.create_line(22, y, w-22, y, fill="#9C7656" if dark else "#BF946E")
        for key in product.CONFIG["room"]["wall_slots"]:
            x = w * {"left": .33, "center": .56, "right": .79}[key]
            identifier = room["wall"].get(key)
            if identifier:
                self._wall_item(identifier, x, 18+(top-18)*.50)
            elif self.on_select:
                cy = 18+(top-18)*.50
                c.create_rectangle(x-50, cy-55, x+50, cy+55, outline="#94B3C9", dash=(4, 4))
                c.create_text(x, cy, text="墙面槽位", fill="#9DB4C7" if dark else "#7592A6", font=("Microsoft YaHei UI", 10))
        if self.on_select:
            for col in range(9):
                c.create_line(left+col*cw, top+2, left+col*cw, top+4*ch, fill="#A6A399" if dark else "#CEC3B1", dash=(2, 5))
            for row in range(5):
                c.create_line(left, top+row*ch, left+8*cw, top+row*ch, fill="#A6A399" if dark else "#CEC3B1", dash=(2, 5))
        for _, placed in sorted(room["placements"].items(), key=lambda item: (item[1]["y"], item[1]["x"])):
            self._furniture(placed["item"], left+placed["x"]*cw, top+placed["y"]*ch, cw, ch)
        if self.preview:
            item, location = product.CATALOG[self.preview["item"]], self.preview["location"]
            color = "#448FD0" if self.preview["valid"] else "#CD746B"
            if item["kind"] == "furniture" and "x" in location:
                x, y = left+location["x"]*cw, top+location["y"]*ch
                c.create_rectangle(x+2,y+2,x+item["width"]*cw-2,y+item["height"]*ch-2,outline=color,width=3,dash=(5,3))
                if self.preview["valid"]:
                    self._furniture(self.preview["item"], x, y, cw, ch)
            elif item["kind"] == "wall" and "slot" in location:
                x = w * {"left": .33, "center": .56, "right": .79}[location["slot"]]
                cy = 18+(top-18)*.50
                c.create_rectangle(x-50, cy-55, x+50, cy+55, outline=color, width=3, dash=(5,3))
                if self.preview["valid"]:
                    self._wall_item(self.preview["item"], x, cy)
        if not room["placements"] and not room["wall"]:
            c.create_text(w*.57, top+ch, text="我的家，从这一间空房开始", fill="#8FA3B2" if dark else "#8B8174",
                          font=("Microsoft YaHei UI", 14))
        pose = "sleep" if product.active_hero(self.g)["energy"] <= 0 else "idle"
        actor_size = min(115, round(h*.30))
        self._actor = self.sprites.actor_photo(self.g, pose, actor_size)
        c.create_image(w-actor_size*.76, h-actor_size*.52, image=self._actor)

    def _wall_item(self, identifier, x, y):
        c = self.canvas
        if getattr(self, "sprites", None):
            _, _, _, top, _, _ = self._geometry()
            picture = self.sprites.item_photo_fit(identifier, top*.72, top*.65)
            if picture:
                self._room_images.append(picture)
                c.create_image(x, y, image=picture)
                return
        if identifier == "home_window":
            self._round(x-45,y-43,x+45,y+43,"#F6FAFD",4)
            c.create_rectangle(x-37,y-35,x+37,y+35,fill="#AEDCF1",outline="")
            c.create_oval(x+11,y-28,x+28,y-11,fill="#FFF0A9",outline="")
            c.create_oval(x-33,y-3,x+5,y+10,fill="#F9FCFF",outline="")
            c.create_rectangle(x-3,y-35,x+3,y+35,fill="#F6FAFD",outline="")
            c.create_rectangle(x-37,y-3,x+37,y+3,fill="#F6FAFD",outline="")
        else:
            self._round(x-36,y-29,x+36,y+29,"#B18B63",5)
            c.create_rectangle(x-29,y-22,x+29,y+22,fill="#DAEAF0",outline="")
            c.create_polygon(x-26,y+17,x-7,y-8,x+10,y+14,x+20,y-3,x+27,y+17,fill="#89AB97",outline="")
            c.create_oval(x+11,y-15,x+20,y-6,fill="#E9C77A",outline="")

    def _furniture(self, identifier, x, y, cw, ch):
        c, item = self.canvas, product.CATALOG[identifier]
        if getattr(self, "sprites", None):
            _, h, _, _, _, _ = self._geometry()
            picture = self.sprites.item_photo_fit(identifier, item["width"]*cw-10,
                                                   ch*1.3 if identifier == "home_rug" else h*.38)
            if picture:
                self._room_images.append(picture)
                c.create_image(x+item["width"]*cw/2, y+item["height"]*ch-5, image=picture, anchor="s")
                return
        width, height = item["width"]*cw-12, item["height"]*ch-7
        x, foot = x+6, y+height
        if identifier == "home_bed":
            self._round(x,foot-height,x+width,foot,"#A47859",6)
            self._round(x+5,foot-height+3,x+width-5,foot-6,"#8CAFD8",6)
            self._round(x+7,foot-height+5,x+width*.36,foot-height*.45,"#F8F9FC",4)
            c.create_line(x+width*.4,foot-height+5,x+width*.4,foot-6,fill="#C1D5ED",width=2)
        elif identifier == "home_washer":
            self._round(x+6,foot-ch*1.55,x+width-4,foot,"#EAF0F3",6)
            c.create_rectangle(x+10,foot-ch*1.4,x+width-8,foot-ch*1.16,fill="#B7CBD4",outline="")
            cx, cy, radius = x+width/2, foot-ch*.62, min(width*.29,ch*.46)
            c.create_oval(cx-radius-3,cy-radius-3,cx+radius+3,cy+radius+3,fill="#89A8BC",outline="")
            c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill="#4C7189",outline="")
            c.create_arc(cx-radius+4,cy-radius+4,cx+radius-4,cy+radius-4,start=200,extent=115,outline="#C0D9E5",width=3,style="arc")
        elif identifier == "home_desk":
            c.create_rectangle(x+10,foot-height*.85,x+16,foot,fill="#946E51",outline="")
            c.create_rectangle(x+width-16,foot-height*.85,x+width-10,foot,fill="#946E51",outline="")
            self._round(x,foot-height,x+width,foot-height*.72,"#C7966B",4)
            for i,color in enumerate(("#699CB9","#BD8794","#7DA993")):
                c.create_rectangle(x+13+i*7,foot-height-13,x+19+i*7,foot-height,fill=color,outline="")
            c.create_rectangle(x+width*.55,foot-height-5,x+width*.83,foot-height,fill="#FAF8EC",outline="")
        elif identifier == "home_shelf":
            self._round(x+5,foot-ch*1.7,x+width-5,foot,"#B18A67",4)
            for row in range(3):
                sy=foot-ch*1.5+row*ch*.47
                c.create_rectangle(x+10,sy-4,x+width-10,sy+ch*.35,fill="#8B684D",outline="")
                for col,color in enumerate(("#AAC6D8","#D5A38D","#A8BF9C","#C9B6D6")):
                    c.create_rectangle(x+14+col*(width-27)/4,sy,x+19+col*(width-27)/4,sy+ch*.29,fill=color,outline="")
        elif identifier == "home_plant":
            c.create_polygon(x+width*.3,foot-height*.45,x+width*.7,foot-height*.45,x+width*.61,foot,x+width*.39,foot,fill="#C19376",outline="")
            c.create_line(x+width*.5,foot-height*.4,x+width*.5,foot-height*1.3,fill="#518368",width=3)
            for dx,dy in ((-.22,-1.15),(.07,-1.4),(-.15,-.85),(.08,-.98)):
                c.create_oval(x+width*(.5+dx),foot+height*dy,x+width*(.5+dx+.22),foot+height*(dy+.35),fill="#77A78B",outline="")
        elif identifier == "home_rug":
            self._round(x,foot-height*.78,x+width,foot,"#AAB9DA",12)
            c.create_text(x+width/2,foot-height*.38,text="✦",fill="#F6EAD0",font=("Microsoft YaHei UI",17))
        elif identifier == "home_sofa":
            self._round(x+3,foot-height*1.05,x+width-3,foot,"#D0AE86",8)
            self._round(x+8,foot-height*.72,x+width-8,foot-7,"#E7C7A3",5)
            c.create_line(x+width*.5,foot-height*.68,x+width*.5,foot-9,fill="#BD9A73")
        else:
            self._round(x+width*.2,foot-height*1.35,x+width*.8,foot-height*.55,"#709EC8",5)
            self._round(x+width*.13,foot-height*.65,x+width*.87,foot-height*.28,"#9BBBE0",5)
            c.create_line(x+width*.22,foot-height*.25,x+width*.22,foot,fill="#8A6D55",width=3)
            c.create_line(x+width*.78,foot-height*.25,x+width*.78,foot,fill="#8A6D55",width=3)
