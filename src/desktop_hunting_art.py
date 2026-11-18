"""复用冒险地图的收服演出。演出只读取已保存结果，不执行结算。"""
from __future__ import annotations
import copy
from collections import OrderedDict
import math
import time
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import game
from game_art import AdventureScene
import desktop_product as product
import desktop_hunting as hunting
import store
from desktop_hunting_effects import draw_projectile, draw_ultimate

class HuntingScene(ctk.CTkFrame):
    def __init__(self,master,sprites,g,target,*,biome='forest',height=155,**kwargs):
        super().__init__(master,height=height,corner_radius=16,**kwargs)
        self.pack_propagate(False)
        self.sprites=sprites;self.g=g;self.target=target
        self._companions_snapshot=(hunting.active(g) or {}).get('companions_snapshot')
        self.biome=next(b for b in game.BIOMES if b['id']==biome)
        self._background_key=None;self._background_photo=None
        self._target_key=None;self._target_photo=None;self._target_photos=OrderedDict();self._ball_photo=None
        self._reduced_motion=g.get('product',{}).get('settings',{}).get('reduced_motion',False)
        self.projectile_kind=hunting.SPIRITS.get(target,{}).get('projectile','question')
        self.send_seconds=.08 if self._reduced_motion else .42
        self.enemy_pose='idle';self._on_complete=None
        self.pose='idle';self.effect=None;self.effect_started=0;self.count=None;self._animation_id=None
        self._ultimate=None
        self._static_key=None
        self.canvas=tk.Canvas(self,highlightthickness=0,bd=0);self.canvas.pack(fill='both',expand=True,padx=3,pady=3)
        self.canvas.bind('<Configure>',lambda event:self.redraw())

    def _enemy(self,size,pose='idle'):
        if self.target in product.HEROES:
            preview=product.hero_preview(self.g,self.target)
            preview['finance_expansion']=copy.deepcopy(preview.get('finance_expansion',{}));preview['finance_expansion'].update(companion=None,companions=[])
            return self.sprites.actor_photo(preview,'hurt' if pose=='sad' else pose,size)
        item=hunting.SPIRITS[self.target]
        asset=item.get('poses',{}).get(pose,item['asset'])
        key=(self.target,asset,size)
        if key not in self._target_photos:
            path=store.resource_path('assets/'+asset)
            if not path.is_file():return None
            source=self.sprites._read(path).copy();source.thumbnail((size,size),Image.Resampling.LANCZOS)
            self._target_photos[key]=ImageTk.PhotoImage(source)
            while len(self._target_photos)>8:self._target_photos.popitem(last=False)
        self._target_photos.move_to_end(key)
        self._target_photo=self._target_photos[key];self._target_key=key
        return self._target_photo

    def redraw(self):
        if not self.winfo_exists():return
        c=self.canvas;w=max(300,c.winfo_width());height=max(100,c.winfo_height());sc=self._get_widget_scaling()
        dark=ctk.get_appearance_mode()=='Dark'
        key=(w,height,dark,self.biome['id'])
        if self._static_key != key:
            c.configure(bg=self.biome['dark' if dark else 'light']);c.delete('all')
            AdventureScene._draw_landscape(self,c,w,height,self.biome['color'],dark)
            self._static_key=key
        else:
            for tag in ('dynamic','hunt_ultimate','hunt_projectile'):c.delete(tag)
        size=min(round(145*sc),round(height*.94));x,y=w*.23,height*.56
        elapsed=max(0,time.monotonic()-self.effect_started)
        if self.effect=='ultimate' and not self._reduced_motion:
            x+=math.sin(elapsed*85)*self._ultimate['power']*3*max(0,1-abs(elapsed-.38)*5)
        if self._reduced_motion and self.effect in ('captured','failed','escape'):elapsed=2.1
        pose='celebrate' if self.effect=='captured' and elapsed>.7 else 'hurt' if self.effect in ('failed','escape') and elapsed>.7 else self.pose
        from finance import companion_render_state
        actor=companion_render_state(self.g,self._companions_snapshot)
        self._hero_photo=self.sprites.actor_photo(actor,pose,size);c.create_image(x,y,image=self._hero_photo,tags='dynamic')
        enemy_pose='send' if self.effect in ('send','ultimate') else 'celebrate' if self.effect=='captured' and elapsed>.7 else 'sad' if self.effect in ('failed','escape') and elapsed>.7 else self.enemy_pose
        enemy=self._enemy(size,enemy_pose);ex=w*.77
        if self.effect in ('failed','escape') and elapsed>.7 and not self._reduced_motion:ex+=w*min(1,(elapsed-.7)/1.2)
        if self.effect=='captured' and elapsed>.7:
            if enemy:c.create_image(ex,y,image=enemy,tags='dynamic')
            for i in range(0 if self._reduced_motion else 12):
                angle=i*math.tau/12;radius=min(65*sc,(elapsed-.7)*70*sc)
                px,py=w*.77+math.cos(angle)*radius,y+math.sin(angle)*radius
                c.create_oval(px-3,py-3,px+3,py+3,fill='#FFDA77',outline='',tags='dynamic')
        elif enemy:c.create_image(ex,y,image=enemy,tags='dynamic')
        if self.count is not None:
            c.create_text(w*.5,height*.45,text=str(self.count),fill='#FFFFFF',font=('Microsoft YaHei UI',round(40*sc),'bold'),tags='dynamic')
        if self.effect=='send':
            t=.55 if self._reduced_motion else min(1,elapsed/self.send_seconds)
            px=w*(.77-.43*t);py=height*(.5-.12*math.sin(t*math.pi))
            draw_projectile(c,self.projectile_kind,px,py,sc,t,rarity=hunting.SPIRITS.get(self.target,{}).get('rarity','common'))
        if self.effect=='ultimate' and self._ultimate:
            draw_ultimate(c,self._ultimate,w,height,sc,.55 if self._reduced_motion else min(1,elapsed/.6),reduced_motion=self._reduced_motion)
        if self.effect in ('captured','failed','escape'):
            path=store.resource_path('assets/hunting/yuanbao_ball.png')
            if path.is_file() and self.effect!='escape' and not self._reduced_motion:
                ball_size=round(45*sc)
                if self._ball_photo is None or self._ball_photo.width()!=ball_size:
                    self._ball_photo=ImageTk.PhotoImage(self.sprites._read(path).resize((ball_size,ball_size),Image.Resampling.LANCZOS))
                t=min(1,elapsed/.7);bx=w*(.23+.54*t);by=height*.58-math.sin(math.pi*t)*height*.38
                c.create_image(bx,by,image=self._ball_photo,tags='dynamic')
            if elapsed>1.1:
                c.create_text(w*.5,height*.21,text='收服成功！' if self.effect=='captured' else '精灵逃走了…',fill='#FFE6A1' if self.effect=='captured' else '#E6F1FF',font=('Microsoft YaHei UI',round(18*sc),'bold'),tags='dynamic')

    def play(self,effect,*,on_complete=None,ultimate=None):
        if self._animation_id:self.after_cancel(self._animation_id)
        self.effect=effect;self.effect_started=time.monotonic();self.count=None
        self._animation_id=None;self._on_complete=on_complete
        self._ultimate=ultimate
        if self._reduced_motion and effect!='send':
            self.redraw();callback=self._on_complete;self._on_complete=None
            if callback:callback()
            return
        self._animate()

    def _animate(self):
        self._animation_id=None
        if not self.winfo_exists():return
        duration=self.send_seconds if self.effect=='send' else .6 if self.effect=='ultimate' else 2.1
        deadline=self.effect_started+duration
        if time.monotonic()<deadline:
            self.redraw()
            # 绘制也占用演出时间；冷图片/缩放绘制后不能再等待绘制前的剩余时长。
            remaining=deadline-time.monotonic()
            if remaining>0:
                delay=math.ceil(remaining*1000) if self._reduced_motion else min(40,math.ceil(remaining*1000))
                self._animation_id=self.after(max(1,delay),self._animate)
                return
        if self.effect in ('send','ultimate'):self.effect=None
        self.redraw();callback=self._on_complete;self._on_complete=None
        if callback:callback()

    def destroy(self):
        self._on_complete=None
        if self._animation_id:
            try:self.after_cancel(self._animation_id)
            except tk.TclError:pass
        self._animation_id=None;self._target_photos.clear()
        super().destroy()
