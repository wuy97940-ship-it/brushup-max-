"""5.2电脑成长与全模式计时界面，复用原题渲染及原子保存。"""
from __future__ import annotations

import copy
import math
import random
import time
from tkinter import messagebox
import uuid

import customtkinter as ctk
from PIL import Image
from app import C, _f, btn_ghost, btn_primary, btn_soft
import desktop_growth as growth
import desktop_product as product
import finance
import store
from desktop_persistence import save_with_events, waiting, defer_close
from desktop_window_resources import release_resources, ManagedWindow
from finance_ui import analysis_text
from learning_explanations import explanation_text, is_audit


class GrowthUIMixin:
    def __init__(self):
        self._growth_tick_id = None
        self._background_warm_id = None
        self._quiz_visible = False
        self._timer_samples = {}
        self._deferred_auto_next = False
        self._pending_timeout = False
        self._arming_key = None
        self._basic_remaining = []
        self._cast_window = None
        self._pending_cast_skill = None
        super().__init__()
        self._growth_tick_id = self.after(200,self._growth_tick)
        self._background_warm_id=self.after(500,self.sprites.warm_backgrounds_async)

    def _show_page(self,name,builder=None):
        self._quiz_visible = False
        return super()._show_page(name,builder)

    def _hero_status_text(self, text, g):
        text = super()._hero_status_text(text, g)
        if not growth.enabled(g):return text
        lines=text.split('\n')
        lines[0]+=' · '+growth.view(g)['title']
        return '\n'.join(lines)

    def _show_migration_notice(self):
        migration = product.state(self.g)['migration']
        if migration.get('acknowledged'):
            return
        text = '已升级电脑版5.3.0。旧题、学习成绩、角色、背包与家园完整保留。\n'
        text += f"原经验 {migration.get('growth_original_xp',0)} 保留，成长补偿 {migration.get('growth_credit',0)}，等级不会降低。\n"
        text += f"旧技能次数及魔法墨水已归档，金币补偿 {migration.get('skill_refund',0)}。\n"
        text += '每天主动完成10道不同题，所有已解锁主角免扣10点体力。\n挑战客观60秒、主观8分钟加等级；自由学习与错题练习不限时。旧挑战续办也遵守新版计时。'
        if migration.get('backup_path'):
            text += '\n旧档备份：'+migration['backup_path']
        messagebox.showinfo('5.3存档升级说明',text)
        self._commit(lambda p:product.state(p['game'])['migration'].update(acknowledged=True))

    def _top_card(self):
        children = self.page_area.winfo_children()
        card = self._card_frame(self.page_area)
        args = {'fill':'x','padx':22,'pady':8}
        if children:
            args['before'] = children[0]
        card.pack(**args)
        return card

    def _build_home(self):
        super()._build_home()
        if not product.state(self.g)['starter_claimed']:
            return
        d, v = growth.daily_view(self.g), growth.view(self.g)
        card = self._top_card()
        self._today_task_label = ctk.CTkLabel(card,text=f"今日10题 · {d['count']}/10  {'已达标，全员免扣点' if d['qualified'] else '还差'+str(d['remaining'])+'题'}",font=_f(16,'bold'),text_color=C['brand'])
        self._today_task_label.pack(anchor='w',padx=16,pady=(10,4))
        self._text(card,f"{v['title']} · 本级经验 {v['within']}/{v['required']} · 连续达标 {d['streak']} 天 · 历史最佳 {d['best_streak']} 天",size=11)
        row = ctk.CTkFrame(card,fg_color='transparent');row.pack(fill='x',padx=16,pady=(4,10))
        btn_soft(row,text='继续闯关',height=29,command=lambda:self._open_world(self.g['world'] if self.g['world'] in {w['id'] for w in self.g['product_campaign']['worlds']} else 'accounting')).pack(side='left',padx=(0,8))
        btn_soft(row,text='薄弱题优先 · 10题',height=29,command=self._weak_daily).pack(side='left',padx=(0,8))
        btn_ghost(row,text='成长与荣誉 →',height=29,command=lambda:self._show_page('growth')).pack(side='left')

    def _weak_daily(self):
        qids = product.review_queue(self.g,self.qmap,due_only=False)
        others = [q['id'] for q in self.questions if q['id'] not in qids]
        self._start_qids((qids+others)[:10],'薄弱题优先')

    def _build_growth(self):
        frame, v = self._scroll(), growth.view(self.g)
        self._heading(frame,'成长与里程碑荣誉',f"Lv.{v['level']} · {v['title']} · 总成长经验 {v['xp']} · 金币 {self.g['coins']}")
        card = self._card_frame(frame);card.pack(fill='x',pady=10)
        self._text(card,f"距离下一级还差 {v['required']-v['within']} 经验",size=19,bold=True,color=C['brand'])
        bar = ctk.CTkProgressBar(card,height=12);bar.pack(fill='x',padx=18,pady=12);bar.set(v['within']/v['required'])
        self._text(card,f"本级 {v['within']}/{v['required']} · 挑战客观题 {60+v['level']} 秒 · 主观题 {480+v['level']*10} 秒；学习不限时")
        if v['next_honor']:
            self._text(card,f"下一里程碑：Lv.{v['next_honor']['level']}「{v['next_honor']['name']}」")
        btn_primary(frame,text='进入技能工坊 · 永久学习与升级',command=lambda:self._show_page('workshop',self._build_workshop)).pack(fill='x',pady=8)
        self._heading(frame,'荣誉柜','达到里程碑后永久获得，可选择佩戴；连续学习徽章也收在这里。')
        for h in v['honors']:
            card = self._card_frame(frame);card.pack(fill='x',pady=4)
            self._text(card,f"{'★' if h['unlocked'] else '☆'} Lv.{h['level']} · {h['name']}",size=14,bold=True)
            button = btn_soft(card,text='已佩戴' if v['title']==h['name'] else '佩戴称号' if h['unlocked'] else '继续积累经验',height=28,
                              command=lambda name=h['name']:self._wear_honor(name))
            button.pack(anchor='e',padx=16,pady=(0,10))
            if not h['unlocked'] or v['title']==h['name']:
                button.configure(state='disabled')
        self._text(frame,'连续达标徽章：'+('、'.join(str(n)+'天' for n in growth.state(self.g)['badges']) or '连续完成每日10题，可获得3、7、30天徽章。'))

    def _wear_honor(self,name):
        if self._commit(lambda p:growth.equip_honor(p,name)):
            self._show_page('growth')

    def _build_workshop(self):
        frame = self._scroll()
        self._heading(frame,'里程碑技能工坊',f"Lv.{product.level(self.g)} · 金币 {self.g['coins']} · 主动技能最多三项；精灵羁绊为被动技能。")
        self._text(frame,'0—9级没有技能。达到等级后用金币学习；每提高10级可再提升一阶，升级需金币。')
        if getattr(self,'_bond_unlock_notice',False):
            self._text(frame,'双精灵同行已解锁！到角色馆的精灵图鉴选择第二只伙伴。',size=15,bold=True,color=C['brand'])
            self._bond_unlock_notice=False
        self.workshop_learn_buttons={};self.workshop_equip_buttons={}
        for s in growth.skill_view(self.g):
            card = self._card_frame(frame);card.pack(fill='x',pady=7)
            if growth.passive(s['id']):
                self._npc_picture(card,s['icon'],92).pack(side='left',padx=12,pady=12)
                self._text(card,'精灵伙伴 · 被动羁绊',size=13,bold=True,color=C['brand'])
            else:
                npc = next(n for n in finance.CONFIG['npcs'] if n['id'] == s['npc_id'])
                self._npc_picture(card, npc['asset'], 92).pack(side='left', padx=12, pady=12)
                self._text(card, npc['name'] + ' · 技能导师', size=13, bold=True, color=C['brand'])
            rank_text = ['尚未学习','Ⅰ阶','Ⅱ阶','Ⅲ阶','Ⅳ阶'][s['rank']]
            self._text(card,f"{s['name']} · {rank_text} · Lv.{s['level']}起学",size=17,bold=True,color=C['brand'])
            self._text(card,s['description'])
            self._text(card,self._skill_effect_text(s),size=11)
            row = ctk.CTkFrame(card,fg_color='transparent');row.pack(fill='x',padx=16,pady=(4,12))
            text = '已满阶' if s['maxed'] else f"{'升级' if s['rank'] else '学习'} · Lv.{s['required_level']} · {s['next_price']}金币"
            buy = btn_primary(row,text=text,height=31,command=lambda key=s['id']:self._learn_skill(key));buy.pack(side='left',padx=(0,8))
            self.workshop_learn_buttons[s['id']]=buy
            if not s['allowed']:
                buy.configure(state='disabled')
            if growth.passive(s['id']):
                bond=growth.bond_view(self.g)
                active=bool(bond['rank'] and bond['companions'])
                self._text(card,f"当前：同行{len(bond['companions'])}/{bond['limit']} · {'羁绊已生效' if active else '带一只精灵后生效' if s['rank'] else '学习后随精灵同行生效'}",size=11)
                equip=btn_soft(row,text='去精灵图鉴选择伙伴 →',height=31,command=self._open_spirit_catalog);equip.pack(side='left')
            else:
                equip = btn_soft(row,text='已携带 · 点击卸下' if s['equipped'] else '携带到下一场',height=31,
                                  command=lambda key=s['id']:self._equip_skill(key));equip.pack(side='left')
                if not s['rank']:
                    equip.configure(state='disabled')
            self.workshop_equip_buttons[s['id']]=equip

    def _open_spirit_catalog(self):
        self._role_tab='精灵';self._show_page('roles')

    @staticmethod
    def _skill_effect_text(s):
        if growth.passive(s['id']):
            return ('被动，不耗蓝、不占主动位置。Ⅰ—Ⅳ阶同行名额 '+
                    '／'.join(map(str,s['companions']))+'；金币 '+
                    '／'.join(map(str,s['coins_percent']))+'%；经验 '+
                    '／'.join(map(str,s['xp_percent']))+'%；魔法上限 '+
                    '／'.join(map(str,s['mana_percent']))+'%。')
        costs = 'Ⅰ—Ⅳ阶耗蓝 ' + '／'.join(map(str,s['mana_costs'])) + '；每题同技能一次，无场次数上限。'
        if s['id']=='clock':
            return '客观+'+'／'.join(map(str,s['objective']))+'秒；主观+'+'／'.join(map(str,s['subjective']))+'秒。'+costs
        if s['id']=='insight':
            return '排除'+'／'.join(map(str,s['exclude']))+'个错误选项。'+costs
        if s['id']=='mercy':
            return '错误/超时时自动保护游戏成绩，真实成绩保留。'+costs
        if s['id']=='outline':
            return '最多展示'+'／'.join(map(str,s['lines']))+'条结构提示。'+costs
        return '线索来自原有知识字段。'+costs

    def _npc_picture(self, parent, relative, size):
        path = store.resource_path('assets/' + relative)
        with Image.open(path) as original:
            source = original.convert('RGBA')
        source.thumbnail((size, size), Image.Resampling.LANCZOS)
        picture = ctk.CTkImage(source, size=source.size)
        label = ctk.CTkLabel(parent, text='', image=picture)
        label._npc_image = picture
        return label

    def _show_skill_effect(self, key):
        if growth.passive(key):
            return
        s = growth.SKILLS[key]
        npc = next(n for n in finance.CONFIG['npcs'] if n['id'] == s['npc_id'])
        if self._cast_window and self._cast_window.winfo_exists():
            self._cast_window.destroy()
        win = self._cast_window = ManagedWindow(self)
        win.title(npc['name'] + ' · ' + s['name'])
        win.geometry('400x440')
        win.transient(self)
        relative = s['cast_image'] if store.resource_path('assets/' + s['cast_image']).is_file() else npc['asset']
        self._npc_picture(win, relative, 270).pack(pady=12)
        self._text(win, npc['name'] + '施展「' + s['name'] + '」', size=16, bold=True, color=C['brand'])
        self._text(win, '魔法与效果已保存。关闭窗口不会重复消耗。', size=11)
        btn_soft(win, text='继续作答', command=win.destroy).pack(pady=10)
        win.after(1500, lambda: win.destroy() if win.winfo_exists() else None)

    def _learn_skill(self,key):
        before=growth.companion_limit(self.g)
        if self._commit(lambda p:growth.learn(p,key,uuid.uuid4().hex)):
            if growth.companion_limit(self.g)>before:
                self._bond_unlock_notice=True
            self._show_page('workshop',self._build_workshop)

    def _equip_skill(self,key):
        if self._commit(lambda p:growth.equip(p,key)):
            self._show_page('workshop',self._build_workshop)

    def _build_practice(self):
        super()._build_practice()
        # 沿用选章/题数/难度控件，只替换过时的无计时说明。
        self._replace_text(self.page_area,'没有强制计时，可以暂停','闯关和比武按题型计时，学习不限时')
        card = self._top_card()
        self._text(card,'普通比武按独立真实成绩；技能比武按游戏计分，与NPC娱乐切磋。',size=12)
        self._arena_variant = ctk.CTkSegmentedButton(card,values=['普通比武','技能比武'],font=_f(12))
        self._arena_variant.pack(fill='x',padx=16,pady=10);self._arena_variant.set('普通比武')
        stats = growth.state(self.g)['arena_records']
        self._text(card,'战绩：'+ '  ·  '.join(('普通' if mode=='arena' else '技能')+f" 胜{r['胜']} 平{r['平']} 败{r['败']}" for mode,r in stats.items()) if stats else '技能比武10级开放，两种比武使用本学科跨章节重难点题，共用每日学科奖励资格。',size=11)

    @staticmethod
    def _replace_text(root,old,new):
        for child in root.winfo_children():
            if isinstance(child,ctk.CTkLabel):
                text = str(child.cget('text'))
                if old in text:
                    child.configure(text=text.replace(old,new))
            GrowthUIMixin._replace_text(child,old,new)

    def _start_arena(self):
        mode = 'arena_skills' if self._arena_variant.get()=='技能比武' else 'arena'
        if mode=='arena_skills' and product.level(self.g)<10:
            messagebox.showinfo('技能比武','达到10级后开放技能比武。');return
        world = next(w for w in self.g['product_campaign']['worlds'] if w['name']==self._arena_world.get())
        from desktop_challenge import arena_pool
        pool=arena_pool(self.qmap.values(),world['id'])
        qids=[q['id'] for q in pool]
        random.SystemRandom().shuffle(qids)
        qids.sort(key=lambda qid:(not self.qmap[qid].get('verified_exam',False),
                                 qid not in self.progress['wrong_book'] if self._arena_weak.get() else False))
        requested=int(self._arena_count.get().replace('题',''));qids=qids[:requested]
        if len(qids)<5:
            messagebox.showinfo('重难点题暂不足','本学科目前不足5道经核验的重难点客观题，请先进行基础学习。');return
        if len(qids)<requested:
            messagebox.showinfo('本场题量',f'本学科有{len(qids)}道合格重难点题，本场采用实际题量。')
        rate = 60 if self._arena_difficulty.get().startswith('入门') else 90 if self._arena_difficulty.get().startswith('进阶') else 80
        a = self._commit(lambda p:product.start_practice(p,qids,mode=mode,name=world['name']+' · 重难点'+self._arena_variant.get(),
                         target=math.floor(len(qids)*rate/100),chapter_key='arena550:'+world['id']))
        if a:
            self._open_practice(a)

    def _arena_update_chapters(self):
        self._arena_chapter.configure(values=['全科重难点综合挑战'],state='disabled')
        self._arena_chapter.set('全科重难点综合挑战')

    def _start_qids(self,qids,mode='自选'):
        qids = list(dict.fromkeys(q for q in qids if q in self.qmap))
        self._basic_remaining = qids[10:]
        self._basic_remaining_mode = 'basic'
        super()._start_qids(qids[:10],mode)

    def _start_review(self,due_only=True):
        qids=product.review_queue(self.g,self.qmap,due_only=due_only)
        if not qids:
            messagebox.showinfo('错题复习','暂时没有到期错题。可以去基础学习巩固，或稍后再来。')
            return
        self._start_review_group(qids)

    def _build_quiz(self):
        if not self._game_mode and len(self.current_qids)>10:
            old = self.progress.get('practice')
            if not old or old.get('settled') or old.get('qids')!=self.current_qids:
                self._basic_remaining=list(self.current_qids[10:])
                self.current_qids=list(self.current_qids[:10])
                self.current_idx=0
        self._quiz_visible = True
        return super()._build_quiz()

    def _render_current(self):
        super()._render_current()
        if not self.current_qids:
            return
        a, qid = self._attempt(), self.current_qids[self.current_idx]
        if not growth.current(a):
            return
        q = self.qmap[qid]
        lines = a.get('growth_clues',{}).get(qid,[])
        if lines:
            card = self._card_frame(self.body);card.pack(fill='x',pady=8)
            self._text(card,'技能线索 · '+'\n'.join(lines),size=12,color=C['brand'])
        if qid in a.get('primary_submissions',{}) and qid not in a['answers']:
            box=getattr(self,'user_answer_box',None)
            if not q.get('subquestions') and box and box.winfo_exists():
                box.configure(state='disabled')
            self._text(self.body,'作答已提交，计时停止。请对照参考完成自评，随后保存本次结果。',size=12,color=C['brand'])
        key = (a['id'],qid)
        if growth.timed(a) and not product.death_locked(self.g) and qid not in a['answers'] and qid not in a.get('primary_submissions',{}) and qid not in a['timers'] and self._arming_key != key:
            self._arming_key=key
            self.after_idle(lambda k=key:self._arm_timer(k))
        elif a['answers'].get(qid,{}).get('timeout'):
            self._deferred_auto_next=True

    def _arm_timer(self,key):
        if waiting(self):
            self.after(20,lambda k=key:self._arm_timer(k))
            return
        self._arming_key=None
        if not self._quiz_visible or not self.current_qids or self._pending_transaction:
            return
        a, qid = self._attempt(),self.current_qids[self.current_idx]
        if not a or not growth.timed(a) or product.death_locked(self.g) or (a['id'],qid)!=key or qid in a['answers'] or qid in a.get('primary_submissions',{}):
            return
        self.update_idletasks()
        if self._commit(lambda p:growth.start_timer(p['game'],self._attempt(p),self.qmap[qid])):
            self._render_skill_controls()

    def _render_skill_controls(self):
        if not self.current_qids:
            return
        a = self._attempt()
        if not growth.current(a):
            return super()._render_skill_controls()
        parent = self._skill_controls
        keys = tuple(a['skill_snapshot'])
        # 本场冻结的技能快照不随换题变化；只更新状态，避免起表时再重建一遍。
        identity = (parent, keys, a['product_mode'])
        cached = getattr(self, '_growth_controls_cache', None)
        if not cached or cached['identity'] != identity or not all(
                w.winfo_exists() and w.master is parent for w in cached['widgets']):
            for child in parent.winfo_children():
                child.destroy()
            timer = ctk.CTkLabel(parent, text='', font=_f(12, 'bold'), text_color=C['brand'])
            timer.pack(side='left', padx=(0, 12))
            buttons = {}
            for key in keys:
                button = btn_soft(parent, text='', height=27, font=_f(10),
                                     command=lambda k=key: self._cast_growth_skill(k))
                button.pack(side='left', padx=3)
                buttons[key] = button
            if not keys:
                ctk.CTkLabel(parent, text='普通比武禁用技能' if a['product_mode'] == 'arena' else '10级后可到工坊学习技能',
                               font=_f(10), text_color=C['text_sub']).pack(side='left')
            cached = self._growth_controls_cache = {'identity': identity, 'widgets': tuple(parent.winfo_children()),
                                                   'timer': timer, 'buttons': buttons}
        self._timer_label = cached['timer']
        # 计时文字不属于可禁用技能；复用题卡时恢复原生Label，避免disabledforeground盖过红色。
        if self._timer_label.cget('state') != 'normal':
            self._timer_label.configure(state='normal')
        q = self.qmap[self.current_qids[self.current_idx]]
        qid = q['id']
        color = C['brand']
        if qid in a['answers']:
            text = '已提交 · 解析不限时'
        elif qid in a.get('primary_submissions', {}):
            text = '已提交 · 待核对'
        elif a.get('timers', {}).get(qid, {}).get('status') == 'running':
            n = max(0, math.ceil(self._remaining(a, qid)))
            text = f'剩余 {n//60:02d}:{n%60:02d}'
            color = C['red'] if n <= 10 else color
        else:
            text = '题目准备中…' if growth.timed(a) else '学习不限时'
        if self._timer_label.cget('text') != text or self._timer_label.cget('text_color') != color:
            self._timer_label.configure(text=text, text_color=color)
        for key, button in cached['buttons'].items():
            status = growth.skill_status(self.g, a, q, key)
            text = growth.SKILLS[key]['name'] + ' · ' + str(status['cost']) + '蓝'
            if status['reason']:
                text += '（' + status['reason'] + '）'
            state = 'normal' if status['allowed'] and key != 'mercy' else 'disabled'
            if button.cget('text') != text or button.cget('state') != state:
                button.configure(text=text, state=state)

    def _cast_growth_skill(self,key):
        if not self._guard_deadline():
            return
        self._flush_draft()
        if self._pending_transaction:
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        selection=copy.copy(getattr(self,'current_selection',set()))
        judge=getattr(self,'current_judge','')
        if self._commit(lambda p:growth.use(p,self._attempt(p),q,key)):
            if key=='clock':
                self._render_skill_controls()
            else:
                self._render_current()
                self.current_selection=selection-set(self._attempt().get('hints',{}).get(q['id'],[]))
                self.current_judge=judge
                if not store.is_subjective(q):
                    self._refresh_option_styles(q)
            self._show_skill_effect(key)
        elif self._pending_transaction:
            self._pending_cast_skill = key

    def _remaining(self,a,qid):
        t = a['timers'][qid]
        key = (a['id'],qid)
        now, mono = time.time(),time.monotonic()
        anchor = self._timer_samples.setdefault(key,(t['deadline'],t['deadline']-now,mono))
        if len(self._timer_samples)>64:
            del self._timer_samples[next(iter(self._timer_samples))]
        return min(t['deadline']-now,anchor[1]+t['deadline']-anchor[0]-(mono-anchor[2]))

    def _guard_deadline(self):
        try:
            product.require_action(self.g)
        except ValueError as error:
            messagebox.showinfo('伙伴休眠', str(error))
            return False
        a = self._attempt()
        if not growth.current(a):
            return True
        qid = self.current_qids[self.current_idx]
        t = a['timers'].get(qid)
        if growth.timed(a) and not t:
            return False
        if t and t['status']=='running' and self._remaining(a,qid)<=0:
            self._handle_timeout();return False
        return True

    def _growth_tick(self):
        self._growth_tick_id=None
        if getattr(self,'_closing_app',False) or not self.winfo_exists():
            return
        if waiting(self):
            self._growth_tick_id=self.after(200,self._growth_tick);return
        if not self._pending_transaction:
            if product.day_key()>growth.state(self.g)['last_seen_day']:
                self._commit(lambda p:product.login(p))
                label=getattr(self,'_today_task_label',None)
                if label and label.winfo_exists():
                    d=growth.daily_view(self.g)
                    label.configure(text=f"今日10题 · {d['count']}/10  {'已达标，全员免扣点' if d['qualified'] else '还差'+str(d['remaining'])+'题'}")
            if self._quiz_visible and self.current_qids:
                a, qid = self._attempt(),self.current_qids[self.current_idx]
                if growth.current(a) and product.death_locked(self.g):
                    if hasattr(self, '_timer_label') and self._timer_label.winfo_exists():
                        if self._timer_label.cget('text') != '体力为0 · 请还魂或重开':
                            self._timer_label.configure(text='体力为0 · 请还魂或重开')
                elif growth.current(a):
                    if self._deferred_auto_next and self.winfo_viewable():
                        self._deferred_auto_next=False
                        self._next_q()
                    else:
                        t = a['timers'].get(qid) if growth.timed(a) else None
                        if t and t['status']=='running':
                            remaining = self._remaining(a,qid)
                            if remaining<=0:
                                self._handle_timeout()
                            elif hasattr(self,'_timer_label') and self._timer_label.winfo_exists():
                                n = math.ceil(remaining)
                                text = f'剩余 {n//60:02d}:{n%60:02d}'
                                color = C['red'] if n<=10 else C['brand']
                                if self._timer_label.cget('text') != text or self._timer_label.cget('text_color') != color:
                                    self._timer_label.configure(text=text,text_color=color)
                        elif hasattr(self,'_timer_label') and self._timer_label.winfo_exists():
                            text = '已提交 · 解析不限时' if qid in a['answers'] else '已提交 · 待核对' if qid in a.get('primary_submissions',{}) else '题目准备中…' if growth.timed(a) else '学习不限时'
                            if self._timer_label.cget('text') != text or self._timer_label.cget('text_color') != C['brand']:
                                self._timer_label.configure(text=text, text_color=C['brand'])
        self._growth_tick_id=self.after(200,self._growth_tick)

    def _handle_timeout(self):
        if self._pending_transaction or not self.current_qids or product.death_locked(self.g):
            return
        a, qid = self._attempt(),self.current_qids[self.current_idx]
        if qid in a['answers'] or qid in a.get('primary_submissions',{}):
            return
        q = self.qmap[qid]
        structured = self._finance_capture() if q.get('subquestions') else None
        box = getattr(self,'user_answer_box',None)
        draft = growth.case_text(q,structured) if structured else box.get('1.0','end').strip() if store.is_subjective(q) and box and box.winfo_exists() else ''
        def mutate(p):
            attempt = self._attempt(p)
            if structured:
                attempt.setdefault('structured_drafts',{})[qid]=structured
            return growth.timeout(p,q,attempt,draft,now=max(time.time(),attempt['timers'][qid]['deadline']))
        self._pending_timeout=True
        if self._commit(mutate):
            self._pending_timeout=False
            self._deferred_auto_next=True
            if self.winfo_viewable():
                self._deferred_auto_next=False
                self._next_q()
        elif not self._pending_transaction:
            self._pending_timeout=False

    def _retry_pending(self):
        if waiting(self):return
        if not self._pending_timeout:
            result = super()._retry_pending()
            if not self._pending_transaction and self._pending_cast_skill:
                key, self._pending_cast_skill = self._pending_cast_skill, None
                self._show_skill_effect(key)
            return result
        if not self._pending_transaction:
            return
        candidate,_ = self._pending_transaction
        if not save_with_events(self,store.save_progress,candidate):
            messagebox.showerror('仍未保存','本题超时结果仍未写入，请检查磁盘后重试。');return
        self.progress=candidate
        self._pending_transaction=None
        self._pending_timeout=False
        self._sync_avatar()
        self.retry_save_btn.pack_forget()
        for name in ('_quiz_retry_button', '_quiz_retry_btn'):
            button = getattr(self, name, None)
            if button is not None and button.winfo_exists():
                button.pack_forget()
        self._deferred_auto_next=True

    def _submit_answer(self):
        if self.current_qids and self._guard_deadline():
            return super()._submit_answer()

    def _show_reference_answer(self):
        if not self.current_qids or not self._guard_deadline():
            return
        q = self.qmap[self.current_qids[self.current_idx]]
        if not growth.current(self._attempt()):
            return super()._show_reference_answer()
        if q.get('subquestions'):
            return self._finance_submit()
        text = self.user_answer_box.get('1.0','end').strip()
        def primary(p):
            a=self._attempt(p)
            growth.submit_primary(p,q,a,text)
            a['drafts'][q['id']]=text
            if q['id'] not in a['references']:
                a['references'].append(q['id'])
            return True
        if self._commit(primary):
            super()._show_reference_answer()
            self.user_answer_box.configure(state='disabled')

    def _finance_submit(self):
        if not self.current_qids or not self._guard_deadline():
            return
        q, snapshot = self._finance_question(),self._finance_capture()
        if not growth.current(self._attempt()):
            return super()._finance_submit()
        if q['id'] in self._attempt()['answers']:
            if self._attempt().get('correction_edit',{}).get(q['id']):
                return super()._finance_submit()
            messagebox.showinfo('本题成绩已记录','首次成绩保留，请通过错题复习独立纠正。');return
        def submit(p):
            a=self._attempt(p)
            a.setdefault('structured_drafts',{})[q['id']]=snapshot
            result=finance.prepare_submission(a,q,allow_partial=True)
            text=growth.case_text(q,snapshot)
            growth.submit_primary(p,q,a,text)
            a['drafts'][q['id']]=text
            return result
        if self._commit(submit):
            self._render_current()

    def _finance_grade(self):
        return super()._finance_grade()

    def _after_product_answer(self):
        result=super()._after_product_answer()
        a = self._attempt()
        if a and self.current_qids:
            reward = a.get('product_actions', {}).get(self.current_qids[self.current_idx], {})
            if reward.get('protected'):
                self._show_skill_effect('mercy')
        if hasattr(self,'_timer_label') and self._timer_label.winfo_exists():
            self._timer_label.configure(text='已提交 · 解析不限时')
        return result

    def _show_result(self,result):
        self._deferred_auto_next=False
        super()._show_result(result)
        self._growth_result_panel(result)

    def _show_practice_result(self,result):
        self._deferred_auto_next=False
        super()._show_practice_result(result)
        self._growth_result_panel(result)

    def _growth_result_panel(self,result):
        if 'game_correct' not in result:
            return
        card=self._top_card()
        total=result['total']
        self._text(card,f"真实正确率 {result['correct']/total:.0%} ({result['correct']}/{total}) · 游戏计分 {result['game_correct']/total:.0%} ({result['game_correct']}/{total})",size=17,bold=True,color=C['brand'])
        if result.get('assisted'):
            limit=' · 闯关最高两星' if 'stage_id' in result else ''
            self._text(card,'技能助力'+limit+' · 实际错题与超时记录保留',size=12,bold=True,color=C['brand'])
        v=growth.view(self.g)
        self._text(card,f"本场经验 +{result['xp']} · Lv.{v['level']} · 距离升级还差 {v['required']-v['within']}经验",size=12)
        if 'mood_change' in result:
            self._text(card, f"心情 {result['mood_before']}/100 → {result['mood_after']}/100 · 本次结算 {result['mood_change']:+d}", size=12)
        future=next((s for s in growth.skill_view(self.g) if not s['maxed'] and s['required_level']>v['level']),None)
        if future:
            self._text(card,f"下一技能目标：{future['name']} · 还差{future['required_level']-v['level']}级 · 金币还差{max(0,future['next_price']-self.g['coins'])}",size=11)
        wrong=result.get('wrong_qids',[])
        if wrong:
            btn_soft(card,text=f"本轮复盘 · {len(wrong)}道错题／超时题",height=29,command=lambda:self._review_result(wrong)).pack(anchor='w',padx=16,pady=9)
        if self._basic_remaining:
            remaining=list(self._basic_remaining)
            review=getattr(self,'_basic_remaining_mode','basic')=='review'
            btn_primary(card,text=f'继续下一组 · 还有{len(remaining)}题',height=29,command=lambda:self._start_review_group(remaining) if review else self._start_qids(remaining,'继续学习')).pack(anchor='w',padx=16,pady=7)

    def _review_result(self,qids,page_index=0):
        if isinstance(qids, dict):
            qids=qids.get('wrong_qids', [])
        qids=list(dict.fromkeys(qid for qid in qids if qid in self.qmap))
        pages=max(1, math.ceil(len(qids)/20))
        page_index=max(0,min(page_index,pages-1))
        def build():
            frame=self._scroll()
            self._heading(frame,'本轮错题复盘','查看解析和独立错题练习均不限时。')
            controls=ctk.CTkFrame(frame,fg_color='transparent');controls.pack(fill='x',pady=6)
            btn_ghost(controls,text='上一页',state='normal' if page_index else 'disabled',command=lambda:self._review_result(qids,page_index-1)).pack(side='left')
            self._text(controls,f'第{page_index+1}/{pages}页 · 共{len(qids)}题',size=12)
            btn_ghost(controls,text='下一页',state='normal' if page_index<pages-1 else 'disabled',command=lambda:self._review_result(qids,page_index+1)).pack(side='right')
            for qid in qids[page_index*20:(page_index+1)*20]:
                q=self.qmap[qid]
                card=self._card_frame(frame);card.pack(fill='x',pady=6)
                self._text(card,q['stem'],size=13)
                self._review_images(card,q,'stem_images')
                box=ctk.CTkTextbox(card,height=150,font=_f(12),wrap='char');box.pack(fill='x',padx=16,pady=10)
                box.insert('1.0','参考答案：'+str(q['answer'])+'\n\n'+explanation_text(q)+'\n\n'+analysis_text(q));box.configure(state='disabled')
                self._review_images(card,q,'reference_images')
            btn_primary(frame,text='独立重练这些错题',command=lambda:self._start_review_group(qids)).pack(fill='x',pady=10)
        self._show_page('growth',build)

    def _review_images(self, parent, question, field):
        if field == 'stem_images' and question.get('diagram_id'):
            from question_diagrams import QuestionDiagram
            QuestionDiagram(parent, question['diagram_id']).pack(fill='x', padx=12, pady=8)

    def _start_review_group(self,qids):
        self._basic_remaining=qids[10:]
        self._basic_remaining_mode='review'
        a=self._commit(lambda p:product.start_practice(p,qids[:10],mode='review',name='本轮错题复习'))
        if a:
            self._open_practice(a)

    def _build_finance_town(self):
        super()._build_finance_town()
        card=self._top_card()
        v,d=growth.view(self.g),growth.daily_view(self.g)
        self._text(card,'家园荣誉柜 · '+v['title'],size=16,bold=True,color=C['brand'])
        medals=ctk.CTkFrame(card,fg_color='transparent');medals.pack(fill='x',padx=16,pady=5)
        earned=[h for h in v['honors'] if h['unlocked']][-6:]
        for i,h in enumerate(earned):
            label=ctk.CTkLabel(medals,text=f"✦ Lv.{h['level']} · {h['name']}",font=_f(11,'bold'),
                fg_color=('#EAF1FF','#263C5A'),text_color=C['brand'],corner_radius=8)
            label.grid(row=i//3,column=i%3,sticky='ew',padx=4,pady=4)
            medals.grid_columnconfigure(i%3,weight=1)
        self._text(card,'学习纪念徽章：'+('、'.join(str(n)+'天' for n in d['badges']) or '连续达标3、7、30天可获得徽章'),size=12)
        btn_soft(card,text='查看全部里程碑',height=28,command=lambda:self._show_page('growth')).pack(anchor='w',padx=16,pady=(0,9))

    def destroy(self):
        if defer_close(self):return
        if self._cast_window and self._cast_window.winfo_exists():
            self._cast_window.destroy()
        if self._background_warm_id:
            self.after_cancel(self._background_warm_id);self._background_warm_id=None
        if self._growth_tick_id:
            self.after_cancel(self._growth_tick_id);self._growth_tick_id=None
        self._timer_samples.clear()
        return super().destroy()
