"""独立角色馆、猎场控制器及整套试穿。猎场不走普通十题练习入口。"""
from __future__ import annotations
import copy
import math
import time
import uuid
from tkinter import messagebox
import customtkinter as ctk
from app import App,C,_f,btn_primary,btn_soft,btn_ghost
import desktop_product as product
import desktop_growth as growth
import desktop_hunting as hunting
import desktop_suits as suits
import finance
from desktop_hunting_art import HuntingScene
from desktop_window_resources import release_resources
from game_art import AdventureScene
import store
from desktop_persistence import save_with_events, waiting, defer_close

class HuntingUIMixin:
    def __init__(self):
        from desktop_audio import GameAudio
        self._hunt_audio = GameAudio()
        self._hunt_sfx = GameAudio()
        self._hunt_visible=False;self._hunt_tick_id=None;self._hunt_present_id=None;self._hunt_draft_id=None
        self._hunt_scene=None;self._role_tab='主角';self._hunt_biome='forest';self._suit_hero='xiaoyuan'
        self._hunt_ultimate_block=False
        try:
            super().__init__()
        except BaseException:
            self._hunt_audio.close()
            self._hunt_sfx.close()
            raise
        self._hunt_tick_id=self.after(200,self._hunt_tick)

    def _play_hunt_music(self, track='hunting', *, loop=True):
        settings = product.state(self.g)['settings']
        if track == 'hunting':
            from desktop_audio import SPIRIT_THEMES
            target = (hunting.active(self.g) or {}).get('target')
            theme = SPIRIT_THEMES.get(target)
            if theme:track = theme['track']
        self._hunt_audio.configure(enabled=settings.get('sound', True), volume=settings.get('volume', 50))
        self._hunt_audio.play(track, loop=loop)

    def _play_hunt_effect(self, track):
        settings = product.state(self.g)['settings']
        self._hunt_sfx.configure(enabled=settings.get('sound', True), volume=settings.get('volume', 50))
        self._hunt_sfx.play(track)

    def _cancel_hunt_callbacks(self):
        for field in ('_hunt_present_id','_hunt_draft_id'):
            timer=getattr(self,field,None)
            if timer:
                try:self.after_cancel(timer)
                except Exception:pass
            setattr(self,field,None)

    def _show_page(self,name,builder=None):
        self._hunt_audio.stop()
        self._hunt_sfx.stop()
        self._hunt_ultimate_block=False
        self._hunt_visible=False;self._cancel_hunt_callbacks();self._hunt_scene=None
        return super()._show_page(name,builder)

    def _build_heroes(self):
        if not product.state(self.g)['starter_claimed']:return super()._build_heroes()
        return self._build_roles()

    def _build_roles(self):
        frame=self._scroll();self.current_qids=[]
        self._heading(frame,'角色馆','主角与精灵各有自己的旅程；已拥有的伙伴继续陪你同行。')
        self.roles_tabs=ctk.CTkSegmentedButton(frame,values=['主角','精灵'],font=_f(13),command=self._set_role_tab)
        self.roles_tabs.pack(fill='x',pady=10);self.roles_tabs.set(self._role_tab)
        team=[key for key in finance.companion_ids(self.g) if key in hunting.SPIRITS];limit=growth.companion_limit(self.g)
        self.spirit_equip_buttons={}
        if self._role_tab=='精灵':
            owned=sum(identifier in self.g['inventory'] for identifier in hunting.SPIRITS)
            self._text(frame,f'精灵图鉴 {owned}/{len(hunting.SPIRITS)} · 同行 {len(team)}/{limit}',size=15,bold=True,color=C['brand'])
            names='、'.join(hunting.SPIRITS[identifier]['name'] for identifier in team) or '暂未选择'
            self._text(frame,'当前同行：'+names,size=12)
            if limit==1:
                skill=growth.SKILLS[growth.BOND_SKILL]
                self._text(frame,f"第二个同行名额：精灵羁绊Ⅳ阶解锁 · Lv.{skill['level']+30}；前三阶保持单只同行。",size=11)
            else:
                self._text(frame,'双精灵已开放；收益按羁绊阶数计算一次，满额时请选择替换哪只。',size=11)
        grid=ctk.CTkFrame(frame,fg_color='transparent');grid.pack(fill='x',pady=6)
        for col in range(3):grid.grid_columnconfigure(col,weight=1,uniform='roles')
        self.role_cards={};count=len(hunting.eligible(self.g,self.qmap));s=product.state(self.g);trial=hunting.CONFIG['hero_trial']
        entries=product.HEROES if self._role_tab=='主角' else hunting.SPIRITS
        for index,(identifier,item) in enumerate(entries.items()):
            card=self._card_frame(grid);card.grid(row=index//3,column=index%3,sticky='nsew',padx=5,pady=7)
            image=self.sprites.portrait(product.hero_preview(self.g,identifier),145) if self._role_tab=='主角' else self.sprites.item_icon(identifier,145)
            ctk.CTkLabel(card,text='',image=image,height=150).pack(pady=(12,2))
            self._text(card,item['name'],size=16,bold=True,color=C['brand'])
            self.role_cards[identifier]=card
            ultimate=hunting.ultimate_for('hero_trial' if self._role_tab=='主角' else 'spirit_hunt',identifier)
            if ultimate:
                self._text(card,f"独有大招 · {ultimate['name']}\n收服答题时 {ultimate['chance']*100:g}%概率干扰体力、魔法或时间",size=11,color=C['brand'])
            if self._role_tab=='主角':
                if identifier in s['heroes']:
                    hero=s['heroes'][identifier];self._text(card,f"体力 {hero['energy']/100:g}/{hero['maximum']/100:g}\n魔法 {hero['mana']}/{hero['mana_maximum']}",size=12)
                    current=identifier==product.hero_id(self.g)
                    button=btn_soft(card,text='正在同行' if current else '切换主角',command=lambda key=identifier:self._switch_from_roles(key),state='disabled' if current or hunting.active(self.g) else 'normal')
                elif identifier in hunting.state(self.g)['hero_qualifications']:
                    balance=hunting.state(self.g)['hero_qualifications'][identifier]['balance']
                    self._text(card,f'考试已通过 · 资格永久保留\n待付尾款 {balance}金币',size=12,color=C['brand'])
                    button=btn_primary(card,text=f'支付{balance}金币，迎接伙伴',command=lambda key=identifier:self._pay_hero(key))
                else:
                    self._text(card,f"通关客观题 {count}/{trial['questions']}\n{trial['questions']}题 · 正确率{trial['pass_percent']}%\n定金{trial['deposit']} + 通过后尾款{trial['balance']}",size=12)
                    button=btn_soft(card,text='进入主角考试',command=lambda key=identifier:self._start_hero_hunt(key),state='normal' if count>=trial['questions'] and not hunting.active(self.g) else 'disabled')
            else:
                rarity=hunting.CONFIG['rarities'][item['rarity']]
                self._text(card,rarity['name']+' · '+item['role'],size=11,color=C['brand'])
                if item.get('lore'):
                    self._text(card,item['story']+'\n'+item['lore'],size=11)
                if identifier in self.g['inventory']:
                    current=identifier in team
                    self._text(card,'已收服 · '+('正在同行' if current else '可加入同行'),size=12)
                    state='disabled' if hunting.active(self.g) else 'normal'
                    if not current and limit>1 and len(team)>=limit:
                        self.spirit_equip_buttons[identifier]={}
                        for previous in team:
                            replacement=btn_soft(card,text='替换'+hunting.SPIRITS[previous]['name'],command=lambda key=identifier,old=previous:self._equip_spirit(key,replace=old),state=state)
                            replacement.pack(fill='x',padx=12,pady=(5,5))
                            self.spirit_equip_buttons[identifier][previous]=replacement
                        continue
                    text='取消同行' if current else '替换当前同行' if limit==1 and team else '让它同行'
                    button=btn_soft(card,text=text,command=lambda key=identifier:self._equip_spirit(key),state=state)
                    self.spirit_equip_buttons[identifier]={None:button}
                else:
                    self._text(card,f"未收服 · {rarity['questions']}题\n答题达标后投球成功率{rarity['capture_percent']}%",size=12)
                    button=btn_soft(card,text='前往精灵狩猎',command=lambda:self._show_page('hunting'))
            button.pack(fill='x',padx=12,pady=(8,14))
        btn_soft(frame,text='成套衣柜 · 整套试穿与穿戴 →',command=lambda:self._show_page('suits')).pack(fill='x',pady=10)

    def _set_role_tab(self,value):
        self._role_tab=value;self._show_page('roles')

    def _switch_from_roles(self,identifier):
        if self._commit(lambda p:product.switch_hero(p,identifier)):self._show_page('roles')

    def _equip_spirit(self,identifier,*,replace=None):
        self._role_tab='精灵';r=self._commit(lambda p:hunting.equip_spirit(p,identifier,replace=replace))
        if r:self._hunt_dispatch(r)

    def _build_finance_companions(self):
        self._role_tab='精灵';self._build_roles()

    def _build_hunting(self):
        self.current_qids=[];frame=self._scroll();g=self.g
        count=len(hunting.eligible(g,self.qmap));owned=sum(key in g['inventory'] for key in hunting.SPIRITS);total=len(hunting.SPIRITS)
        self._heading(frame,'精灵狩猎',f'已通关不同客观题 {count}道 · 精灵图鉴 {owned}/{total} · 金币 {g["coins"]}')
        current=hunting.active(g)
        if current:
            target=product.HEROES.get(current['target'],hunting.SPIRITS.get(current['target']))['name']
            card=self._card_frame(frame);card.pack(fill='x',pady=7)
            self._text(card,'上次收服挑战 · '+target,size=17,bold=True,color=C['brand'])
            self._text(card,f"已作答 {len(current['answers'])}/{len(current['qids'])} · 出战主角已锁定。已展示题的截止时间继续有效。")
            self.hunt_resume_button=btn_primary(card,text='继续挑战 →' if current['phase']=='running' else '答题已达标 · 投圆宝球 →',command=self._open_hunt)
            self.hunt_resume_button.pack(fill='x',padx=14,pady=8)
            btn_ghost(card,text='主动弃战',command=self._abandon_hunt).pack(anchor='w',padx=14,pady=(0,8))
        self._text(frame,'选择森林、海岛或星空，场景变化不会影响出现概率。',size=12)
        self.hunt_biome_control=ctk.CTkSegmentedButton(frame,values=['森林','海岛','星空'],command=self._select_hunt_biome,font=_f(12))
        self.hunt_biome_control.pack(fill='x',pady=8);self.hunt_biome_control.set({'forest':'森林','island':'海岛','stars':'星空'}[self._hunt_biome])
        scene=AdventureScene(frame,self.sprites,g,biome=self._hunt_biome,height=145);scene.pack(fill='x',pady=6)
        minimum=hunting.CONFIG['spirit_unlock_questions']
        self.hunt_start_button=btn_primary(frame,text=f'图鉴已完成 · {total}只全部收服' if owned==total else '寻找一只未收服精灵 →',height=40,command=self._start_spirit_hunt,state='normal' if count>=minimum and not current and owned<total else 'disabled')
        self.hunt_start_button.pack(fill='x',pady=8)
        if count<minimum:self._text(frame,f'再通关{minimum-count}道不同客观题即可开放精灵狩猎。',color=C['brand'])
        self._text(frame,"精灵越珍贵，答题与收服要求越高；达标后可投球一次。答对不扣血，答错和挑战失败按下方规则扣血。",size=12)
        for rule in hunting.CONFIG['rarities'].values():
            required=math.ceil(rule['questions']*rule['pass_percent']/100)
            self._text(frame,f"{rule['name']}：{rule['questions']}题 · 每题{rule['seconds']}秒 · 至少答对{required}题 · 答错扣{rule['wrong_points']} · 失败另扣{rule['failure_points']} · 投球成功率{rule['capture_percent']}%",size=12)
        btn_soft(frame,text='挑战尚未拥有的主角 · 进入角色馆',command=lambda:self._show_page('roles')).pack(fill='x',pady=9)
        last=hunting.state(g)['last_result']
        if last:btn_ghost(frame,text='查看上次收服结果',command=lambda:self._show_hunt_result(last,animate=False)).pack(anchor='w',pady=8)

    def _select_hunt_biome(self,value):
        self._hunt_biome={'森林':'forest','海岛':'island','星空':'stars'}[value];self._show_page('hunting')

    def _start_spirit_hunt(self):
        token=uuid.uuid4().hex;r=self._commit(lambda p:hunting.start_spirit(p,self.qmap,token,biome=self._hunt_biome))
        if r:self._hunt_dispatch(r)

    def _start_hero_hunt(self,identifier):
        rule=hunting.CONFIG['hero_trial']
        if not messagebox.askyesno('主角考试',f"挑战{product.HEROES[identifier]['name']}：先付{rule['deposit']}金币定金，{rule['questions']}题正确率达到{rule['pass_percent']}%。失败定金不返还，通过后支付{rule['balance']}金币尾款，资格永久保留。现在开始？"):return
        token=uuid.uuid4().hex;r=self._commit(lambda p:hunting.start_hero(p,self.qmap,identifier,token,biome=self._hunt_biome))
        if r:self._hunt_dispatch(r)

    def _pay_hero(self,identifier):
        token=uuid.uuid4().hex;r=self._commit(lambda p:hunting.pay_balance(p,identifier,token))
        if r:self._hunt_dispatch(r)

    def _abandon_hunt(self):
        a=hunting.active(self.g)
        if not a:return
        if not messagebox.askyesno('放弃本次挑战','本次挑战将结束。主角考试定金不退；精灵挑战执行一次失败额外扣体力。确定弃战？'):return
        token=uuid.uuid4().hex;r=self._commit(lambda p:hunting.abandon(p,a['id'],token))
        if r:self._hunt_dispatch(r)

    def _open_hunt(self):
        a=hunting.active(self.g)
        if not a:return self._show_page('hunting')
        if a['phase']=='ready_to_throw':return self._show_throw_page()
        self._show_page('hunting',self._build_hunt_quiz)

    def _build_hunt_quiz(self):
        a=hunting.active(self.g)
        if not a:return
        self._play_hunt_music()
        self._hide_sidebar();self._clear();self._hunt_visible=True;self._quiz_visible=False
        self._game_mode=False;self.current_qids=list(a['qids']);self.current_idx=a['index']
        self.answer_submitted=False;self.current_selection=set();self.current_judge=None
        self.current_mode='主角考试' if a['kind']=='hero_trial' else '精灵狩猎'
        top=ctk.CTkFrame(self.page_area,fg_color='transparent');top.pack(fill='x',padx=22,pady=(10,2))
        btn_ghost(top,text='← 保存并返回猎场',height=30,width=145,command=self._hunt_back).pack(side='left')
        self.lbl_meta=ctk.CTkLabel(top,text='',font=_f(11));self.lbl_meta.pack(side='left',padx=10)
        self.btn_fav=btn_soft(top,text='☆ 收藏',height=30,width=75,command=self._toggle_favorite_current);self.btn_fav.pack(side='right')
        self._hunt_scene=HuntingScene(self.page_area,self.sprites,self.g,a['target'],biome=a['biome'],height=135)
        self._hunt_scene.pack(fill='x',padx=22,pady=4)
        status=ctk.CTkFrame(self.page_area,fg_color='transparent');status.pack(fill='x',padx=25,pady=3)
        self.lbl_score=ctk.CTkLabel(status,text='',font=_f(12,'bold'),text_color=C['brand']);self.lbl_score.pack(side='left')
        self._hunt_timer_label=ctk.CTkLabel(status,text='题目准备中…',font=_f(12,'bold'),text_color=C['brand']);self._hunt_timer_label.pack(side='right')
        self._build_quiz_mood(status)
        self._hunt_attack_label=ctk.CTkLabel(self.page_area,text='',font=_f(11,'bold'),text_color=C['red'],anchor='w')
        self._hunt_attack_label.pack(fill='x',padx=25,pady=(0,2))
        self.body=ctk.CTkScrollableFrame(self.page_area,fg_color='transparent');self.body.pack(fill='both',expand=True,padx=20,pady=(3,10))
        qid=a['qids'][a['index']]
        if qid in a['answers'] or qid in a['timers']:self._render_hunt_question()
        else:self._hunt_countdown(3 if a['index']==0 else 0,a['id'],qid)

    def _hunt_countdown(self,n,identifier,qid):
        self._hunt_present_id=None;a=hunting.active(self.g)
        if not self._hunt_visible or not a or (a['id'],a['qids'][a['index']])!=(identifier,qid):return
        if n>0:
            self._play_hunt_effect('countdown')
            self._hunt_scene.count=n;self._hunt_scene.redraw()
            self._hunt_timer_label.configure(text='准备接招…')
            self._hunt_present_id=self.after(850,lambda:self._hunt_countdown(n-1,identifier,qid))
        else:
            self._play_hunt_effect('send')
            self._hunt_scene.play('send',on_complete=lambda:self._hunt_projectile_arrived(identifier,qid))

    def _hunt_projectile_arrived(self,identifier,qid):
        a=hunting.active(self.g)
        if not self._hunt_visible or not a or a['phase']!='running' or (a['id'],a['qids'][a['index']])!=(identifier,qid):return
        self._render_hunt_question()

    def _render_hunt_question(self):
        self._hunt_present_id=None;a=hunting.active(self.g)
        if not self._hunt_visible or not a or a['phase']!='running':return
        self.current_idx=a['index'];qid=a['qids'][a['index']];q=self.qmap[qid]
        same_question = getattr(self, '_hunt_rendered_qid', None) == qid and getattr(self, 'stem_box', None) is not None and self.stem_box.winfo_exists()
        from desktop_audio import SPIRIT_THEMES
        theme = SPIRIT_THEMES.get(a['target'])
        self.lbl_meta.configure(text=f"{self.current_mode} · {self.current_idx+1}/{len(a['qids'])} · 辅助技能禁用" + (f" · ♫ {theme['title']}" if theme else ''))
        self.lbl_score.configure(text=f"已答对 {sum(r['correct'] for r in a['answers'].values())} · 通过需要 {math.ceil(len(a['qids'])*a['rules_snapshot']['pass_percent']/100)}题")
        self.btn_fav.configure(text='★ 已收藏' if qid in self.progress['favorites'] else '☆ 收藏')
        self._hunt_ultimate_block=False
        self._hunt_attack_label.configure(text=self._hunt_ultimate_text(a.get('ultimates',{}).get(qid)))
        if same_question:
            App._restore_objective_answer(self,q)
        else:
            from app import display_options
            keys = ('√', '×') if q['type'] == '判断题' else tuple(sorted(display_options(q)))
            reuse = (not q.get('diagram_id') and not q.get('stem_images') and getattr(self, '_objective_keys', None) == keys
                     and getattr(self, '_objective_layout_body', None) is self.body
                     and not getattr(self, '_hunt_had_diagram', False))
            if not reuse:
                for child in self.body.winfo_children():release_resources(child);child.destroy()
            self._objective_reuse = reuse
            App._render_objective(self,q)
            self._objective_reuse = False
            self._finance_source_images(q)
            self._hunt_had_diagram = bool(q.get('diagram_id') or q.get('stem_images'))
            self._hunt_rendered_qid = qid
        self.btn_prev.configure(state='disabled');self.btn_redo.configure(state='disabled',text='首答成绩保留')
        if qid in a['drafts'] and qid not in a['answers']:
            if q['type']=='判断题':self.current_judge=a['drafts'][qid]
            else:self.current_selection=set(a['drafts'][qid])
            self._refresh_option_styles(q)
        if qid not in a['answers']:
            if qid not in a['timers']:
                self._hunt_enable_answer(False);self.update_idletasks()
                self._hunt_present_id=self.after_idle(lambda:self._arm_hunt_timer(a['id'],qid))
            else:self._hunt_enable_answer(True)
        else:
            self._hunt_timer_label.configure(text='已提交 · 解析不限时')
            self._hunt_enable_answer(False)
            self._hunt_scene.pose='happy' if a['answers'][qid]['correct'] else 'hurt';self._hunt_scene.redraw()
        self.update_idletasks()
        canvas=getattr(self.body, '_parent_canvas', None)
        if canvas is not None:canvas.yview_moveto(1 if qid in a['answers'] else 0)

    def _arm_hunt_timer(self,identifier,qid):
        self._hunt_present_id=None;a=hunting.active(self.g)
        if not self._hunt_visible or not a or a['id']!=identifier or qid!=a['qids'][a['index']]:return
        if waiting(self) or self._pending_transaction or not self.winfo_viewable():
            self._hunt_present_id=self.after(200,lambda:self._arm_hunt_timer(identifier,qid));return
        # 控件已完成布局；保存计时起点后才接受按钮/键盘提交。
        r=self._commit(lambda p:hunting.start_timer(p,qid,identifier))
        if r:self._hunt_dispatch(r)

    @staticmethod
    def _hunt_ultimate_text(hit):
        if not hit or not hit.get('triggered'):return ''
        losses=[]
        if hit.get('energy_spent'):losses.append(f"体力 −{hit['energy_spent']/100:g}")
        if hit.get('mana_spent'):losses.append(f"魔法 −{hit['mana_spent']}")
        if hit.get('time_spent'):losses.append(f"答题时间 −{hit['time_spent']:g}秒")
        return hit['skill']+'  ·  '+' / '.join(losses)

    def _hunt_present_ultimate(self,result):
        hit=result.get('ultimate')
        if not self._hunt_visible:return
        self._hunt_attack_label.configure(text=self._hunt_ultimate_text(hit))
        if not hit or not hit.get('triggered'):
            self._hunt_enable_answer(True);return
        self._play_hunt_effect('ultimate')
        a=hunting.active(self.g)
        if not a:return
        identifier=a['id'];qid=a['qids'][a['index']]
        self._hunt_ultimate_block=True;self._hunt_enable_answer(False)
        def finished():
            current=hunting.active(self.g)
            if self._hunt_visible and current and (current['id'],current['qids'][current['index']])==(identifier,qid):
                self._hunt_ultimate_block=False;self._hunt_enable_answer(True)
        self._hunt_scene.play('ultimate',ultimate=hit,on_complete=finished)

    def _hunt_enable_answer(self,enabled):
        a=hunting.active(self.g)
        if not self._hunt_visible or not a:return
        qid=a['qids'][a['index']];done=qid in a['answers']
        for button in getattr(self,'option_buttons',{}).values():button.configure(state='normal' if enabled and not done else 'disabled')
        self.btn_submit.configure(state='normal' if enabled and not done else 'disabled')
        self.btn_next.configure(state='normal' if done else 'disabled')

    def _answer_record(self,qid):
        if self._hunt_visible:
            a=hunting.active(self.g);return a['answers'].get(qid) if a else None
        return super()._answer_record(qid)

    def _attempt(self,progress=None):
        if self._hunt_visible:return hunting.active((self.progress if progress is None else progress)['game'])
        return super()._attempt(progress)

    def _render_current(self):
        if self._hunt_visible:return self._render_hunt_question()
        return super()._render_current()

    def _submit_answer(self):
        if not self._hunt_visible:return super()._submit_answer()
        a=hunting.active(self.g)
        if not a or self._pending_transaction or self.answer_submitted or self._hunt_ultimate_block:return
        q=self.qmap[a['qids'][a['index']]];timer=a['timers'].get(q['id'])
        if not timer:return
        if self._remaining(a,q['id'])<=0:return self._hunt_timeout()
        answer=self.current_judge if q['type']=='判断题' else ''.join(sorted(self.current_selection))
        if not answer:return
        r=self._commit(lambda p:hunting.submit(p,q,answer,a['id']))
        if r:self._hunt_dispatch(r)
        elif self._pending_transaction:self._hunt_enable_answer(False)

    def _toggle_option(self,letter):
        if self._hunt_visible:
            a=hunting.active(self.g)
            if not a or a['qids'][a['index']] not in a['timers'] or self._pending_transaction or self._hunt_ultimate_block:return
        super()._toggle_option(letter)
        if self._hunt_visible and not self.answer_submitted:
            if self._hunt_draft_id:self.after_cancel(self._hunt_draft_id)
            self._hunt_draft_id=self.after(650,self._flush_draft)

    def _toggle_judge(self,value):
        if self._hunt_visible:
            a=hunting.active(self.g)
            if not a or a['qids'][a['index']] not in a['timers'] or self._pending_transaction or self._hunt_ultimate_block:return
        return super()._toggle_judge(value)

    def _flush_draft(self):
        self._hunt_draft_id=None
        if not self._hunt_visible:return super()._flush_draft()
        a=hunting.active(self.g)
        if not a or self._pending_transaction:return
        qid=a['qids'][a['index']]
        if qid in a['answers']:return
        q=self.qmap[qid];text=(self.current_judge or '') if q['type']=='判断题' else ''.join(sorted(self.current_selection))
        if a['drafts'].get(qid,'')==text:return
        def save(p):
            hunting.active(p['game'])['drafts'][qid]=text
            return {'flow':'hunting','operation':'draft','attempt_id':a['id']}
        self._commit(save)

    def _hunt_back(self):
        self._flush_draft()
        if self._pending_transaction:return
        self.current_qids=[];self._show_page('hunting')

    def _back_home(self):
        if self._hunt_visible:return self._hunt_back()
        return super()._back_home()

    def _next_q(self):
        if not self._hunt_visible:return super()._next_q()
        a=hunting.active(self.g)
        if not a:return
        r=self._commit(lambda p:hunting.advance(p,a['id']))
        if r:self._hunt_dispatch(r)

    def _prev_q(self):
        if not self._hunt_visible:return super()._prev_q()

    def _redo_current(self):
        if not self._hunt_visible:return super()._redo_current()

    def _hunt_tick(self):
        self._hunt_tick_id=None
        if getattr(self,'_closing_app',False) or not self.winfo_exists():return
        if waiting(self):
            self._hunt_tick_id=self.after(200,self._hunt_tick);return
        if not self._pending_transaction:
            a=hunting.active(self.g)
            if a and product.death_locked(self.g):
                r=self._commit(hunting.fail_if_dead)
                if r:self._hunt_dispatch(r)
            elif self._hunt_visible and a and a['phase']=='running':
                qid=a['qids'][a['index']];t=a['timers'].get(qid)
                if t and t['status']=='running':
                    n=math.ceil(self._remaining(a,qid))
                    if n<=0:self._hunt_timeout()
                    else:self._hunt_timer_label.configure(text=f'剩余 {n//60:02d}:{n%60:02d}',text_color=C['red'] if n<=10 else C['brand'])
        self._hunt_tick_id=self.after(200,self._hunt_tick)

    def _hunt_timeout(self):
        a=hunting.active(self.g)
        if not a or self._pending_transaction:return
        qid=a['qids'][a['index']]
        if qid in a['answers'] or qid not in a['timers']:return
        # 墙钟回拨时仍采用双钟已观察到的截止，不刷新题目。
        moment=max(time.time(),a['timers'][qid]['deadline'])
        r=self._commit(lambda p:hunting.submit(p,self.qmap[qid],a['drafts'].get(qid,''),a['id'],now=moment,timeout=True))
        if r:
            self._hunt_dispatch(r)
        elif self._pending_transaction:self._hunt_enable_answer(False)

    def _show_throw_page(self):
        def build():
            self._play_hunt_music()
            a=hunting.active(self.g)
            if not a:return
            frame=self._scroll();target=hunting.SPIRITS[a['target']];r=a['rules_snapshot']
            self._heading(frame,'答题达标！',f"{target['name']} · 正确 {sum(x['correct'] for x in a['answers'].values())}/{len(a['qids'])}")
            self._hunt_scene=HuntingScene(frame,self.sprites,self.g,a['target'],biome=a['biome'],height=230);self._hunt_scene.pack(fill='x',pady=10)
            self._text(frame,f"你获得一次圆宝球机会，成功率{r['capture_percent']}%。投球失手会额外扣{r['failure_points']}点体力，挑战随后结束。",size=14)
            self.hunt_throw_button=btn_primary(frame,text='投出圆宝球 →',height=44,command=self._throw_hunt_ball);self.hunt_throw_button.pack(fill='x',pady=12)
            btn_ghost(frame,text='保存并稍后回来',command=lambda:self._show_page('hunting')).pack(pady=8)
        self.current_qids=[];self._show_page('hunting',build)

    def _throw_hunt_ball(self):
        a=hunting.active(self.g)
        if not a:return
        token=uuid.uuid4().hex;r=self._commit(lambda p:hunting.throw_ball(p,a['id'],token))
        if r:self._hunt_dispatch(r)

    def _show_hunt_result(self,result,*,animate=True):
        def build():
            if animate:
                self._play_hunt_music('success' if result['phase'] in ('captured', 'awaiting_payment') else 'failure', loop=False)
            frame=self._scroll();target=product.HEROES.get(result['target'],hunting.SPIRITS.get(result['target']))
            pending=result['phase']=='awaiting_payment';captured=result['phase']=='captured'
            self._heading(frame,'考试通过 · 资格已保留' if pending else '伙伴加入了！' if captured else '这次差一点，再来挑战吧',target['name'])
            historical=next((x for x in reversed(hunting.state(self.g)['history']) if x['id']==result.get('attempt_id')),None)
            biome=historical['biome'] if historical else self._hunt_biome
            self._hunt_scene=HuntingScene(frame,self.sprites,self.g,result['target'],biome=biome,height=215);self._hunt_scene.pack(fill='x',pady=9)
            if animate and result['kind']=='spirit_hunt':
                ball=bool(historical and 'capture_roll' in historical)
                if ball:self._play_hunt_effect('throw')
                self._hunt_scene.play('captured' if captured else 'failed' if ball else 'escape')
            else:
                self._hunt_scene.pose='celebrate' if pending or captured else 'hurt'
                self._hunt_scene.enemy_pose='celebrate' if pending or captured else 'sad';self._hunt_scene.redraw()
            if 'correct' in result:self._text(frame,f"正确 {result['correct']}/{result['total']} · "+result.get('reason',''),size=17,bold=True,color=C['brand'])
            if pending:
                balance=result['balance'];self._text(frame,f'支付{balance}金币即可确定获得主角。金币不足时去学习攒钱，资格永久保留。',size=14)
                btn_primary(frame,text=f'支付{balance}金币尾款',command=lambda:self._pay_hero(result['target'])).pack(fill='x',pady=10)
            if result['kind']=='hero_trial' and not result.get('passed'):
                deposit=historical.get('rules_snapshot',{}).get('deposit',hunting.CONFIG['hero_trial']['deposit']) if historical else hunting.CONFIG['hero_trial']['deposit']
                self._text(frame,f"本场考试定金 {deposit}金币已支付；未通过不退还。",size=12)
            elif result.get('failure_energy') is not None:
                self._text(frame,f"失败额外消耗 {result['failure_energy']:g}点体力，已经保存。",size=12)
            btn_primary(frame,text='去角色馆查看伙伴',command=lambda:self._show_page('roles')).pack(fill='x',pady=7)
            btn_soft(frame,text='返回精灵狩猎',command=lambda:self._show_page('hunting')).pack(fill='x',pady=7)
            wrong=result.get('wrong_qids',[])
            if wrong:btn_ghost(frame,text=f'复盘本场{len(wrong)}道错题',command=lambda:self._review_result(wrong)).pack(pady=7)
        self.current_qids=[];self._show_page('hunting',build)

    def _hunt_dispatch(self,result):
        if result.get('flow')=='roles':return self._show_page('roles')
        if result.get('flow')=='suits':return self._show_page('suits')
        op=result.get('operation')
        if op=='draft':return
        if op=='timer':
            self._hunt_present_ultimate(result)
            return
        if result.get('phase') in ('captured','failed','awaiting_payment'):return self._show_hunt_result(result)
        if op=='ready_to_throw':return self._show_throw_page()
        if op=='answer':
            current = hunting.active(self.g)
            rec = current['answers'].get(result['qid'], {}) if current else {}
            self._play_hunt_effect('correct' if rec.get('correct') else 'wrong')
            self._render_hunt_question() if self._hunt_visible else self._open_hunt()
            if result.get('timeout') and hunting.active(self.g) and hunting.active(self.g)['phase']=='running':
                self._hunt_present_id=self.after(700,self._next_q)
            return
        if op=='advance' and self._hunt_visible:
            current = hunting.active(self.g)
            if current and current['phase'] == 'running':
                self._cancel_hunt_callbacks()
                self.answer_submitted = False
                self.current_idx = current['index']
                self._hunt_scene.g = self.g
                self._hunt_scene._reduced_motion = product.state(self.g)['settings'].get('reduced_motion',False)
                self._hunt_scene.send_seconds = .08 if self._hunt_scene._reduced_motion else .42
                self._hunt_scene.pose = 'idle'
                self._hunt_enable_answer(False)
                self._hunt_countdown(0, current['id'], current['qids'][current['index']])
                return
        return self._open_hunt()

    def _retry_pending(self):
        if waiting(self):return
        if self._pending_slot is not None:return self._load_game_slot(self._pending_slot)
        if self._pending_transaction and isinstance(self._pending_transaction[1],dict) and self._pending_transaction[1].get('flow')=='saves':return self._retry_session_save()
        if not self._pending_transaction:return
        candidate,result=self._pending_transaction
        if not isinstance(result,dict) or result.get('flow') not in ('hunting','roles','suits'):return super()._retry_pending()
        if not save_with_events(self,store.save_progress,candidate):
            messagebox.showerror('仍未保存','同一候选结果仍保留，请检查磁盘空间和权限后再试。');return
        self.progress=candidate;self._pending_transaction=None;self.retry_save_btn.pack_forget();self._sync_avatar()
        self._hunt_dispatch(result)

    def _build_equipment_slots(self,parent):
        super()._build_equipment_slots(parent)
        btn_soft(parent,text='成套衣柜 · 整套试穿与一键穿戴 →',command=lambda:self._show_page('suits')).pack(fill='x',pady=6)

    def _build_suits(self):
        frame=self._scroll();self.current_qids=[]
        self._heading(frame,'成套衣柜','四件配齐会切换完整套装形象；混搭继续逐件显示，七槽属性照常计算。')
        labels={item['name']:key for key,item in product.HEROES.items()}
        if self._suit_hero not in product.HEROES:self._suit_hero=product.hero_id(self.g)
        control=ctk.CTkSegmentedButton(frame,values=list(labels),command=lambda value:self._set_suit_hero(labels[value]),font=_f(12))
        control.pack(fill='x',pady=9);control.set(product.HEROES[self._suit_hero]['name'])
        self.suit_cards={};grid=ctk.CTkFrame(frame,fg_color='transparent');grid.pack(fill='x',pady=9)
        for i,item in enumerate(s for s in suits.SUITS.values() if s['hero']==self._suit_hero):
            card=self._card_frame(grid);card.grid(row=i//2,column=i%2,sticky='nsew',padx=5,pady=6)
            preview=suits.preview(self.g,item['id']);ctk.CTkLabel(card,text='',image=self.sprites.portrait(preview,155),height=160).pack(pady=(12,2))
            self._text(card,item['name'],size=16,bold=True,color=C['brand'])
            absent=suits.missing(self.g,item['id']);self._text(card,'四件已齐' if not absent else f'还缺{len(absent)}件',size=12)
            for key in item['required_items'].values():self._text(card,('✓ ' if product.owned_count(self.g,key) else '○ ')+product.SHOP_CATALOG[key]['name'],size=11)
            btn_soft(card,text='整套试穿 · 查看动作',command=lambda key=item['id']:self._open_suit_preview(key)).pack(fill='x',padx=12,pady=6)
            if absent:button=btn_soft(card,text='查看缺件并购买',command=lambda ids=absent:self._open_suit_missing(ids))
            else:button=btn_primary(card,text='一键穿戴四件',command=lambda key=item['id']:self._equip_suit(key),state='normal' if item['hero'] in product.state(self.g)['heroes'] else 'disabled')
            button.pack(fill='x',padx=12,pady=(4,14));self.suit_cards[item['id']]=card
        def arrange(event=None):
            width=(event.width if event else self.page_area.winfo_width())/self._get_widget_scaling()
            columns=max(1,min(3,int(max(1,width-20)//235)))
            for column in range(3):grid.grid_columnconfigure(column,weight=1 if column<columns else 0,uniform='suits' if column<columns else '')
            for index,card in enumerate(self.suit_cards.values()):card.grid_configure(row=index//columns,column=index%columns)
        grid.bind('<Configure>',arrange);arrange()

    def _set_suit_hero(self,identifier):
        self._suit_hero=identifier;self._show_page('suits')

    def _open_suit_preview(self,identifier,*,from_shop=False):
        from desktop_window_resources import ManagedWindow
        item=suits.SUITS[identifier];win=ManagedWindow(self);win.title(item['name']+' · 整套试穿');win.geometry('570x625')
        preview=suits.preview(self.g,identifier)
        names={'idle':'站立','walk':'行走','think':'思考','attack':'出招','happy':'开心','hurt':'受伤',
               'celebrate':'庆祝','chest':'展示','wink':'眨眼','surprise':'惊讶','tired':'疲惫','sleep':'睡觉',
               'smile':'微笑','wave':'挥手','proud':'得意','sad':'难过','cry':'哭泣'}
        choices={names.get(key,'动作'+str(index+1)):key for index,key in enumerate(item['poses'])}
        pose=ctk.StringVar(value=names['idle'])
        preview_label=ctk.CTkLabel(win,text='',image=self.sprites.portrait(preview,330));preview_label.pack(pady=12)
        ctk.CTkOptionMenu(win,values=list(choices),variable=pose,
                          command=lambda value:preview_label.configure(image=self.sprites.portrait(preview,330,choices[value])),font=_f(13)).pack(pady=8)
        self._text(win,'试穿不保存，不消耗金币；可查看完整动作和睡姿。',size=12)
        if from_shop:
            status=suits.shop_status(self.g,identifier)
            win.item_id=identifier;win.missing_items=status['missing_items']
            text=f"已拥有 {status['owned_parts']}/4 件"
            if status['missing_items']:text+=f" · 补齐需 {status['missing_coins']} 金币"
            self._text(win,text+' · 沿用四件单品价格与属性',size=12,color=C['brand'])
            def act():
                win.destroy()
                absent=suits.missing(self.g,identifier)
                if absent:self._open_suit_missing(absent,return_to='shop')
                else:self._equip_suit(identifier)
            unlocked=item['hero'] in product.state(self.g)['heroes']
            # 注意：不得命名为 label——上方换图回调的闭包捕获同名局部变量，此处赋 str 会让点击动作下拉时报 'str' object has no attribute 'configure'。
            action_text='查看缺件并购买' if status['missing_items'] else '一键穿戴四件' if unlocked else '伙伴未收服 · 可先试穿'
            win.action_button=btn_soft(win,text=action_text,command=act,state='normal' if status['missing_items'] or unlocked else 'disabled')
            win.action_button.pack(fill='x',padx=25,pady=7)
        btn_ghost(win,text='结束试穿',command=win.destroy).pack(pady=15)
        win.after(30,win.lift)
        return win

    def _open_suit_missing(self,identifiers,*,return_to='suits'):
        def build():
            frame=self._scroll();self._heading(frame,'套装缺件','按原价购买缺少的单件；四件配齐后可一键穿戴。')
            self.suit_missing_ids=list(identifiers)
            for key in identifiers:
                card=self._card_frame(frame);card.pack(fill='x',pady=7)
                item=product.SHOP_CATALOG[key];self._text(card,item['name'],size=16,bold=True,color=C['brand'])
                btn_soft(card,text='查看商品并购买',command=lambda identifier=key:self._open_market_detail(identifier)).pack(anchor='w',padx=14,pady=8)
            self.suit_missing_return=btn_ghost(frame,text='返回商店套装' if return_to=='shop' else '返回成套衣柜',command=lambda:self._show_page('shop',lambda:self._build_store('装备',subcategory='套装')) if return_to=='shop' else self._show_page(return_to))
            self.suit_missing_return.pack(pady=10)
        self._show_page('suits',build)

    def _equip_suit(self,identifier):
        token=uuid.uuid4().hex;r=self._commit(lambda p:suits.equip(p,identifier,token))
        if r:self._hunt_dispatch(r)

    def destroy(self):
        if defer_close(self):return
        self._hunt_audio.close()
        self._hunt_sfx.close()
        self._cancel_hunt_callbacks()
        if self._hunt_tick_id:
            try:self.after_cancel(self._hunt_tick_id)
            except Exception:pass
        return super().destroy()
