"""存档记录、独立新局和切换失败恢复；两局包含完整学习及游戏状态。"""
from __future__ import annotations
import copy
from tkinter import messagebox
import customtkinter as ctk
from app import C, _f, btn_ghost, btn_primary, btn_soft
import desktop_product as product
import desktop_save_slots as slots
import store
from desktop_persistence import save_with_events, waiting, defer_close

class SaveUIMixin:
    def __init__(self):
        self._pending_slot=None
        super().__init__()
        if not self._pending_transaction:
            slots.ensure_current(store.app_data_dir(),self.progress)

    def _commit(self,mutate):
        if waiting(self):return None
        if self._pending_slot is not None:
            messagebox.showinfo('存档切换待恢复','请先点击「重试保存」，完成同一存档的切换。')
            return None
        return super()._commit(mutate)

    def _reset_session_view(self):
        self.current_qids=[];self._game_mode=False;self._practice_skills_enabled=False
        self._starter_selected=None;self._basic_remaining=[];self._pending_timeout=False
        self._arming_key=None;self._deferred_auto_next=False;self._pending_cast_skill=None
        self._last_feedback_pose=None
        for child in list(self.winfo_children()):
            if isinstance(child,ctk.CTkToplevel):child.destroy()

    def _on_reset(self):
        self._flush_draft()
        if self._pending_transaction or self._pending_slot is not None:return
        previous=self.progress.get("reset_epoch")
        super()._on_reset()
        if self.progress.get("reset_epoch")!=previous:
            self._reset_session_view();self._show_page("home")

    def _retry_session_save(self):
        if waiting(self):return
        candidate,result=self._pending_transaction
        if not save_with_events(self,store.save_progress,candidate):
            messagebox.showerror("仍未保存","同一新局候选仍保留，请检查磁盘空间和权限后重试。");return
        self.progress=candidate;self._pending_transaction=None;self.retry_save_btn.pack_forget()
        self._reset_session_view();self._sync_avatar();self._show_page("home")

    def _build_save_records(self):
        self._flush_draft()
        frame=self._scroll()
        self._heading(frame,'存档记录','每局自动保存最新学习与游戏进度；最多保留两局，可随时继续。')
        self.save_record_cards={}
        try:records=slots.records(store.app_data_dir())
        except (OSError,ValueError) as error:
            self._text(frame,'无法读取存档记录：'+str(error),color=C['brand']);return
        for item in records:
            card=self._card_frame(frame);card.pack(fill='x',pady=8)
            self._text(card,f"游戏 {item['sequence']}"+(' · 当前自动存档' if item['active'] else ' · 可继续的存档'),size=18,bold=True,color=C['brand'])
            if item['available']:
                self._text(card,'最新保存：'+item['saved_at'],size=12)
                self._text(card,f"已刷 {item['answered']} 题 · 错题 {item['wrong']} · 收藏 {item['favorites']} · 金币 {item['coins']}",size=12)
                name=product.HEROES.get(item['hero'],{}).get('name','尚未选择')
                self._text(card,f"主角：{name} · 已获主角 {item['heroes']} · 背包 {item['inventory']} 件；技能、家园、装备和未结束场次一并保存。",size=11)
            else:self._text(card,'此存档无法读取，请保留现有资料并恢复备份。',size=12)
            button=btn_soft(card,text='当前游戏 · 已自动保存' if item['active'] else '继续这个存档',
                            state='disabled' if item['active'] or not item['available'] else 'normal',
                            command=lambda key=item['id']:self._load_game_slot(key))
            button.pack(anchor='w',padx=14,pady=(5,12))
            self.save_record_cards[item['id']]={'record':item,'button':button,'frame':card}
        btn_ghost(frame,text='刷新最新记录',command=lambda:self._show_page('saves')).pack(anchor='w',pady=9)

    def _build_restart_game(self):
        frame=self._scroll()
        self._heading(frame,'重新开始游戏','开始一局新的冒险，从初始欢迎界面重新选择免费主角。')
        card=self._card_frame(frame);card.pack(fill='x',pady=10)
        self._text(card,'当前局会先保存完整进度，再开启新局。',size=17,bold=True,color=C['brand'])
        self._text(card,'存档记录最多保留两局；已有两局时，新局会替换较早的存档点。')
        self._text(card,'新局的作答、错题、收藏、金币、角色、技能、背包、家园和任务均从初始状态开始。')
        self.restart_game_button=btn_primary(frame,text='保存当前局并开始新游戏',command=self._on_reset)
        self.restart_game_button.pack(fill='x',pady=15)
        btn_ghost(frame,text='先查看存档记录',command=lambda:self._show_page('saves')).pack(anchor='w',pady=5)

    def _load_game_slot(self,identifier):
        if self._pending_transaction:
            messagebox.showinfo('还有待保存的进度','请先重试保存，再切换存档。');return
        self._flush_draft()
        if self._pending_transaction:return
        try:
            candidate=slots.restore(store.app_data_dir(),identifier)
        except (OSError,ValueError) as error:
            if slots.pending_switch(store.app_data_dir()):
                self._pending_slot=identifier
                self.retry_save_btn.pack(fill='x',padx=16,pady=4)
            messagebox.showerror('存档切换未完成','两局记录已保留。请重试同一存档或重新打开程序恢复。\n'+str(error))
            return
        self._pending_slot=None
        self.progress=candidate;self._product_ready=False;self.current_qids=[]
        self._reset_session_view()
        self._sync_avatar();self.retry_save_btn.pack_forget()
        self._show_page('home')

    def _retry_pending(self):
        if self._pending_slot is not None:return self._load_game_slot(self._pending_slot)
        return super()._retry_pending()

    def _on_close(self):
        if defer_close(self):return
        if self._pending_slot is not None:
            self._load_game_slot(self._pending_slot)
            if self._pending_slot is not None:return
        return super()._on_close()
