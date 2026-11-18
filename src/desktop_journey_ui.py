"""6.1冒险主城、全篇章路线和非强制伙伴引导。"""
import math
import customtkinter as ctk
from app import C, _f, btn_primary, btn_soft, btn_ghost
import desktop_product as product
import desktop_growth as growth
import desktop_mood as mood
import desktop_journey as journey
from game_art import AdventureScene
import world_scenes


class JourneyUIMixin:
    def _show_page(self, name, builder=None):
        result = super()._show_page(name, builder)
        if (not self._product_booting and not self._pending_transaction
                and product.state(self.g)['starter_claimed'] and self._product_page == name
                and name in journey.CONFIG['guide'] and name not in ('home', 'world', 'chapter', 'worlds')):
            children = self.page_area.winfo_children()
            card = self._journey_guide(self.page_area, name)
            if card and children:
                card.configure(width=224)
                card.pack(side='right' if self.page_area.winfo_width() >= 1050 else 'top',
                          fill='y' if self.page_area.winfo_width() >= 1050 else 'x',
                          before=children[0], padx=12, pady=10)
        return result

    def _build_sidebar(self):
        super()._build_sidebar()
        self.nav_btns['home'].configure(text='◇  冒险主城')
        self.version_label.configure(text='v6.1.0 · 四世界冒险')

    def _journey_guide(self, parent, context):
        state = journey.guide(self.g)
        if state['dismissed'] or context in state['seen'] or context not in journey.CONFIG['guide']:
            return None
        card = self._card_frame(parent)
        title, text = journey.CONFIG['guide'][context]
        ctk.CTkLabel(card, text='', image=self.sprites.portrait(self.g, 64)).pack(pady=(12, 0))
        self._text(card, '伙伴小提示', color=C['brand'], size=11)
        self._text(card, title, bold=True, size=14)
        label = self._text(card, text, size=12)
        label.configure(wraplength=190)
        def finish(all_tips=False):
            if self._commit(lambda p: journey.set_guide(p, context, dismissed=True if all_tips else None)):
                # 保留当前页面和滚动位置，不因关闭提示重复构建地图。
                card.grid_remove() if card.winfo_manager() == 'grid' else card.pack_forget()
        btn_soft(card, text='知道了，继续探索', height=30, command=finish).pack(fill='x', padx=12, pady=(8, 4))
        btn_ghost(card, text='跳过全部引导', height=28, command=lambda: finish(True)).pack(fill='x', padx=12, pady=(0, 12))
        self._guide610_card = card
        return card

    def _journey_shell(self, context):
        scroll = self._scroll()
        shell = ctk.CTkFrame(scroll, fg_color='transparent')
        shell.pack(fill='both', expand=True)
        body = ctk.CTkFrame(shell, fg_color='transparent')
        body.grid(row=0, column=0, sticky='nsew')
        shell.grid_columnconfigure(0, weight=1)
        guide = self._journey_guide(shell, context)
        if guide:
            guide.configure(width=224)
            guide.grid(row=0, column=1, sticky='new', padx=(14, 0))
            layout = [True]  # 初始已按宽屏放置，避免首个Configure重复排布。
            def arrange(event):
                if event.width < 150:
                    return
                wide = event.width >= shell._get_widget_scaling() * 810
                if layout[0] == wide:
                    return
                layout[0] = wide
                if wide:
                    body.grid_configure(row=0, column=0)
                    if not journey.guide(self.g)['dismissed'] and context not in journey.guide(self.g)['seen']:
                        guide.grid(row=0, column=1, sticky='new', padx=(14, 0), pady=0)
                else:
                    body.grid_configure(row=1, column=0)
                    if not journey.guide(self.g)['dismissed'] and context not in journey.guide(self.g)['seen']:
                        guide.grid(row=0, column=0, sticky='ew', padx=0, pady=(0, 10))
            shell.bind('<Configure>', arrange)
        return body

    def _build_home(self):
        self._game_mode = False
        frame = self._journey_shell('home')
        self._heading(frame, '冒险主城 · 今天也向前一步', '地图闯关是主线，四大知识世界，等你点亮。')
        hero = product.active_hero(self.g)
        daily = growth.daily_view(self.g)
        card = self._card_frame(frame)
        card.pack(fill='x', pady=(6, 12))
        self._today_task_label = ctk.CTkLabel(card, text=f"今日10题 · {daily['count']}/10  " + ('已达标，全员免扣点' if daily['qualified'] else f"还差{daily['remaining']}题"), font=_f(15, 'bold'), text_color=C['brand'])
        self._today_task_label.pack(anchor='w', padx=16, pady=(12, 3))
        self._text(card, f"Lv.{product.level(self.g)} · 心情 {mood.value(hero)}/100 · {mood.label(hero)}", size=11)
        summary = product.state(self.g).get('offline_summary')
        if summary and summary.get('days'):
            losses = '、'.join(f"{product.HEROES[key]['name']} {points:g}点" for key, points in summary.get('heroes', {}).items())
            self._text(card, f"已结算{summary['days']}个未完成10题的自然日：{losses or '各伙伴体力已为0'}。每日达标，所有伙伴免扣。", size=11)
        target = journey.next_main(self.g)
        self._main610_target = target
        if target:
            item = self.g['product_campaign']['levels'][target]
            self._text(card, item['chapter_title'] + ' · ' + item['name'], size=13, bold=True)
        else:
            self._text(card, '这个世界已经全部点亮，去看看其它世界吧。', size=13)
        self.main_story_button = btn_primary(card, text='继续主线 →' if target else '探索四大世界 →', height=42,
            command=self._continue_main610)
        self.main_story_button.pack(fill='x', padx=14, pady=(4, 8))
        row = ctk.CTkFrame(card, fg_color='transparent'); row.pack(fill='x', padx=14, pady=(0, 12))
        btn_ghost(row, text='薄弱题优先 · 10题', height=28, command=self._weak_daily).pack(side='left')
        btn_ghost(row, text='心情补给', height=28, command=self._open_mood_shop).pack(side='right')
        if hero['energy'] <= 0:
            recovery = self._card_frame(frame); recovery.pack(fill='x', pady=(0, 12))
            self._text(recovery, '体力为0，请选择还魂或重新开始。学习和施法暂停，商店、背包与历史仍可查看。', color=C['red'], bold=True)
            btn_primary(recovery, text='还魂 · 600金币', command=lambda: self._show_page('shop')).pack(fill='x', padx=14, pady=(4, 6))
            btn_soft(recovery, text='重新开始整个游戏', command=self._on_reset).pack(fill='x', padx=14, pady=(0, 12))
        self._heading(frame, '四大知识世界', '全部篇章可见 · 逐关探索 · 通关点亮')
        self._world_cards610(frame)
        self._heading(frame, '冒险之外，也有新收获', '每个板块独立进入，随时回到主城继续主线。')
        entries = [('practice', '比武场', '检验薄弱知识，选择模式切磋', self._build_practice),
                   ('hunting', '精灵狩猎', '挑战目标，收服新的同行伙伴', self._build_hunting),
                   ('roles', '角色馆', '查看主角、精灵与出战伙伴', self._build_roles),
                   ('growth', '成长与技能', '经验、荣誉与永久技能', self._build_growth),
                   ('town', '经营小镇', '经营旅程与我的家园', self._build_finance_town),
                   ('bag', '我的背包', '整理装备、补给和收藏', self._build_bag),
                   ('shop', '圆宝团大商店', '按需购买，准备冒险补给', self._build_store),
                   ('workshop', '技能工坊', '学习升级与出战配置', self._build_workshop)]
        grid = ctk.CTkFrame(frame, fg_color='transparent'); grid.pack(fill='x', pady=8)
        grid.grid_columnconfigure((0, 1), weight=1, uniform='modules')
        self._module610_buttons = {}
        for i, (key, title, text, builder) in enumerate(entries):
            # 一个完整入口承载名称和说明，避免为八个入口各建重复卡框和文字画布。
            button = btn_soft(grid, text=title + ' →\n' + text, height=70, width=0,
                              font=_f(12), anchor='w', command=lambda k=key, b=builder: self._navigate(k, b))
            button.grid(row=i // 2, column=i % 2, sticky='nsew', padx=4, pady=5)
            button._text_label.configure(justify='left')
            self._module610_buttons[key] = button
        module_cards = tuple(grid.winfo_children())
        module_columns = [2]
        def arrange_modules(event):
            if event.width < 150: return
            columns = 2 if event.width >= grid._get_widget_scaling() * 540 else 1
            if module_columns[0] == columns: return
            module_columns[0] = columns
            for col in range(2):
                grid.grid_columnconfigure(col, weight=1 if col < columns else 0,
                                          uniform='modules' if col < columns else '', minsize=0)
            for index, card in enumerate(module_cards):
                card.grid_configure(row=index // columns, column=index % columns)
        grid.bind('<Configure>', arrange_modules)

    def _continue_main610(self):
        target = journey.next_main(self.g)
        if target:
            self._start_stage(target)
        else:
            self._show_page('home')

    def _world_cards610(self, parent):
        grid = ctk.CTkFrame(parent, fg_color='transparent'); grid.pack(fill='x', pady=6)
        self._home_world_cards = []; self._home_world_grid = grid; self._home_world_columns = 2
        grid.grid_columnconfigure((0, 1), weight=1, uniform='worlds')
        for i, world in enumerate(self.g['product_campaign']['worlds']):
            config = journey.CONFIG['worlds'][world['id']]
            card = self._card_frame(grid); card.grid(row=i // 2, column=i % 2, sticky='nsew', padx=4, pady=5)
            self._home_world_cards.append(card)
            scene = AdventureScene(card, self.sprites, self.g, biome=world['biome'], height=112)
            scene.pack(fill='x', padx=7, pady=(7, 0))
            self._text(card, world['name'], size=17, bold=True, color=config['color'])
            chapters = [journey.chapter_view(self.g, world, ch) for ch in world['chapters']]
            count = sum(ch['clears'] for ch in chapters); total = sum(ch['total'] for ch in chapters)
            self._text(card, config['region'] + '\n' + f"点亮 {count}/{total} 关 · 篇章 {sum(ch['completed'] for ch in chapters)}/{len(chapters)}", size=11)
            bar = ctk.CTkProgressBar(card, height=6, progress_color=config['color']); bar.pack(fill='x', padx=14, pady=7)
            bar.set(count / total if total else 0)
            btn_primary(card, text='进入世界 →', height=33, command=lambda wid=world['id']: self._open_world(wid)).pack(fill='x', padx=12, pady=(2, 12))
        def arrange(event):
            if event.width < 150: return
            columns = 2 if event.width >= grid._get_widget_scaling() * 540 else 1
            if columns == self._home_world_columns: return
            self._home_world_columns = columns
            for col in range(2):
                grid.grid_columnconfigure(col, weight=1 if col < columns else 0,
                                          uniform='worlds' if col < columns else '', minsize=0)
            for i, card in enumerate(self._home_world_cards):
                card.grid_configure(row=i // columns, column=i % columns)
        grid.bind('<Configure>', arrange)

    def _open_world(self, world_id):
        if not self._commit(lambda p: p['game'].update(world=world_id)): return
        def build():
            frame = self._journey_shell('world')
            world = next(w for w in self.g['product_campaign']['worlds'] if w['id'] == world_id)
            config = journey.CONFIG['worlds'][world_id]
            btn_ghost(frame, text='← 冒险主城', command=lambda: self._show_page('home')).pack(anchor='w', pady=4)
            self._heading(frame, world['name'] + ' · ' + config['region'], config['intro'])
            self._chapter610_cards = []
            for chapter in world['chapters']:
                view = journey.chapter_view(self.g, world, chapter)
                card = self._card_frame(frame); card.pack(fill='x', pady=6)
                self._chapter610_cards.append((chapter['id'], card, view['status']))
                self._text(card, f"{'★' if view['completed'] else '◇' if view['available'] else '○'}  第{chapter['number']}章 · {chapter['title']}", bold=True, size=15,
                    color=config['color'] if view['available'] or view['completed'] else C['text_sub'])
                self._text(card, f"{view['place']} · {view['status']} · 点亮 {view['clears']}/{view['total']} 关", size=11)
                self._text(card, view['story'], size=12)
                bar = ctk.CTkProgressBar(card, height=5, progress_color=config['color']); bar.pack(fill='x', padx=14, pady=7)
                bar.set(view['clears'] / view['total'])
                btn_soft(card, text='重访篇章地图 →' if view['completed'] else '查看篇章地图 →', height=31,
                    command=lambda cid=chapter['id']: self._open_chapter(cid)).pack(anchor='e', padx=14, pady=(2, 12))
        self._show_page('home', build)

    def _open_chapter(self, chapter_id):
        if not chapter_id.startswith('v5:'): return super()._open_chapter(chapter_id)
        def build():
            frame = self._journey_shell('chapter')
            g = self.g
            world = next(w for w in g['product_campaign']['worlds'] if any(ch['id'] == chapter_id for ch in w['chapters']))
            chapter = next(ch for ch in world['chapters'] if ch['id'] == chapter_id)
            view = journey.chapter_view(g, world, chapter)
            btn_ghost(frame, text='← ' + world['name'], command=lambda: self._open_world(world['id'])).pack(anchor='w', pady=4)
            self._heading(frame, chapter['title'], view['place'] + ' · ' + view['story'])
            self._text(frame, '普通关80%通关 · Boss90%通关 · 已通关可重打，奖励按原规则结算。', size=11)
            self._text(frame, f"{view['status']} · 点亮 {view['clears']}/{view['total']} 关", bold=True, color=C['brand'])
            for offset in range(0, len(chapter['stages']), 10):
                keys = chapter['stages'][offset:offset + 10]
                nodes = [{'id': key, 'name': g['product_campaign']['levels'][key]['name'],
                    'stars': g['results'].get(key, {}).get('best_stars', 0), 'available': product.can_play(g, key),
                    'kind': g['product_campaign']['levels'][key]['kind'],
                    'cleared': bool(g['results'].get(key, {}).get('cleared')),
                    'current': key == product.next_stage(g, world_id=world['id'])} for key in keys]
                scene = AdventureScene(frame, self.sprites, g, biome=world['biome'],
                    scene_id=world_scenes.chapter_scene(g, world['id'], chapter_id), height=110 * math.ceil(len(keys) / 4) + 45,
                    nodes=nodes, on_node=self._select_stage)
                scene.pack(fill='x', pady=6)
            for key in chapter['stages']:
                item = g['product_campaign']['levels'][key]; result = g['results'].get(key, {})
                row = self._card_frame(frame); row.pack(fill='x', pady=3)
                label = '★' * result.get('best_stars', 0)
                self._text(row, f"{item['name']} · {len(item['qids'])}题  {label}", size=12)
                btn_soft(row, text='重打' if result.get('cleared') else '开始' if product.can_play(g, key) else '查看前置条件',
                    height=29, command=lambda sid=key: self._select_stage(sid)).pack(anchor='e', padx=12, pady=(0, 8))
        self._show_page('home', build)

    def _build_tools(self):
        super()._build_tools()
        card = self._card_frame(self.page_area)
        children = self.page_area.winfo_children()
        card.pack(fill='x', padx=22, pady=10, before=children[0])
        self._text(card, '冒险指南', bold=True, size=15)
        btn_soft(card, text='重新查看伙伴引导 →', command=self._replay_guide610).pack(anchor='w', padx=14, pady=(4, 12))

    def _replay_guide610(self):
        if self._commit(lambda p: journey.set_guide(p, reset=True)):
            self._show_page('home')

    def _show_result(self, result):
        super()._show_result(result)
        item = self.g['product_campaign']['levels'].get(result.get('stage_id'))
        if not item:
            return
        world = next(w for w in self.g['product_campaign']['worlds'] if w['id'] == item['world_id'])
        chapter = next(ch for ch in world['chapters'] if ch['id'] == item['chapter_id'])
        view = journey.chapter_view(self.g, world, chapter)
        card = self._top_card()
        self._text(card, '篇章点亮 · ' + chapter['title'] if view['completed'] else '主线旅程 · ' + view['place'], bold=True, size=15, color=journey.CONFIG['worlds'][world['id']]['color'])
        self._text(card, view['story'] if result.get('passed') else '这一段还需要再练一练。看看解析和错题，准备好后我们一起再出发。', size=12)
        self._text(card, f"本章已点亮 {view['clears']}/{view['total']} 关", size=11)

    def _build_quiz(self):
        # 引导随用户主动展开；不覆盖题干，也不占用计时期间的操作区域。
        super()._build_quiz()
        if not hasattr(self, 'lbl_meta') or not self.lbl_meta.winfo_exists():
            return
        self.quiz_help610 = btn_ghost(self.lbl_meta.master, text='答题指南', width=72, height=28, font=_f(10),
            command=self._quiz_help610)
        self.quiz_help610.pack(side='right', padx=4)

    def _quiz_help610(self):
        from tkinter import messagebox
        if self._quiz_visible and self._attempt() and growth.timed(self._attempt()) and not self.answer_submitted:
            messagebox.showinfo('答题指南', '选中答案后按当前题型提交。单选与判断会直接提交；多选需要点提交答案。最后10秒数字变红。\n\n本题计时仍在继续，提交后可不限时查看解析。')
        else:
            messagebox.showinfo('答题指南', '按题型选择答案并提交，查看解析后点击下一题。多选需要选全；单选与判断会直接提交。\n\n地图闯关计入主线进度；普通关80%、Boss90%通关。')
