"""5.2成长、计时、永久技能规则；所有操作由调用方原子保存。"""
from __future__ import annotations

import copy
from datetime import date, timedelta
import json
import math
import re
import time

import store

CONFIG = json.loads(store.resource_path('assets/growth_config.json').read_text(encoding='utf-8'))
SKILLS = {s['id']: s for s in CONFIG['skills']}
RULESET = '5.3.0'
BOND_SKILL = 'spirit_bond'

def state(g):
    return g['product']['growth']

def enabled(g):
    return g.get('product', {}).get('version') == 3 and 'growth' in g['product']

def current(a):
    return bool(a and a.get('ruleset') == RULESET)

def timed(a):
    return current(a) and a.get('product_mode', 'adventure') in CONFIG['timer']['timed_modes']

def passive(skill_id):
    return SKILLS.get(skill_id, {}).get('kind') == 'passive'

def bond_rank(g):
    if not enabled(g):
        return 0
    skill = SKILLS[BOND_SKILL]
    learned = max(0, min(4, int(state(g)['skills'].get(BOND_SKILL, 0))))
    if not learned:
        return 0
    allowed = max(0, min(4, (level(g) - skill['level']) // 10 + 1))
    return min(learned, allowed)

def companion_limit(g):
    rank = bond_rank(g)
    return SKILLS[BOND_SKILL]['companions'][rank - 1] if rank else 1

def bond_bonuses(g):
    rank = bond_rank(g)
    if not rank:
        return {'coins':0,'xp':0,'mana':0}
    import finance
    from desktop_hunting import SPIRITS
    together = any(identifier in SPIRITS and identifier in g.get('inventory', [])
                   for identifier in finance.companion_ids(g))
    return {key: SKILLS[BOND_SKILL][key + '_percent'][rank - 1] if rank and together else 0
            for key in ('coins', 'xp', 'mana')}

def bond_view(g):
    import finance
    return {'rank': bond_rank(g), 'limit': companion_limit(g),
            'companions': finance.companion_ids(g)[:companion_limit(g)],
            'bonuses': bond_bonuses(g)}

def mana_unlock_level():
    """第一次可学习主动技能时才有魔法；与技能配置共享同一门槛。"""
    return min((skill['level'] for skill in SKILLS.values() if not passive(skill['id'])), default=None)


def mana_maximum(g, identifier=None):
    import desktop_product as p
    from desktop_market import SLOTS, PERSONAL_SLOTS
    identifier = identifier or p.hero_id(g)
    rule = CONFIG['mana']
    unlock = mana_unlock_level()
    if unlock is None or level(g) < unlock:
        return 0
    base = min(rule['base_ceiling'], rule['base_maximum'] + rule['per_level'] * (level(g) - unlock))
    appearance = p.state(g).get('appearances', {}).get(identifier, {})
    bonus = bond_bonuses(g)['mana']
    for slot in SLOTS:
        item_id = appearance.get(slot) if slot in PERSONAL_SLOTS else g.get('equipment', {}).get(slot)
        item = p.SHOP_CATALOG.get(item_id, {})
        if item_id and p.owned_count(g, item_id) and item.get('fit_character') in (None, identifier):
            bonus += int(item.get('mana_percent', 0))
    return base * (100 + bonus) // 100

def mana_cost(a, skill_id):
    if passive(skill_id):
        return 0
    rank = a.get('skill_snapshot', {}).get(skill_id, 0)
    costs=a.get('challenge_rules',{}).get('skill_costs',{}).get(skill_id,SKILLS[skill_id]['mana_costs'])
    return costs[rank - 1] if rank else 0

def restore_correct_mana(g, question, a, *, correct, assisted, key):
    import desktop_product as p
    if not correct or assisted or not mana_maximum(g):
        return 0
    d = day(g, key=key)
    claimed = d.setdefault('mana_qids', {})
    qid = question['id']
    if qid in claimed:
        return 0
    identifier = a.get('primary_submissions', {}).get(qid, {}).get('hero') or p.hero_id(g)
    hero = p.state(g)['heroes'][identifier]
    # 满蓝也记下资格，不能通过随后消耗再重复提交领蓝。
    gain = min(a.get('challenge_rules',{}).get('mana_restore',CONFIG['mana']['correct_restore']), max(0, mana_maximum(g, identifier) - hero['mana']))
    hero['mana'] += gain
    claimed[qid] = {'hero': identifier, 'gain': gain}
    return gain

def required(level):
    return 120 + 25 * level + level * level

def threshold(level):
    return 120 * level + 25 * level * (level-1)//2 + (level-1)*level*(2*level-1)//6

def effective_xp(g):
    return max(0, int(g.get('xp', 0))) + int(state(g).get('migration_credit', 0)) if enabled(g) else max(0, int(g.get('xp', 0)))

def level(g):
    xp = effective_xp(g)
    lo, hi = 0, 1
    while threshold(hi) <= xp:
        hi *= 2
    while hi-lo > 1:
        mid = (lo+hi)//2
        if threshold(mid) <= xp:
            lo = mid
        else:
            hi = mid
    return lo

def view(g):
    lv = level(g)
    honors = copy.deepcopy(CONFIG['honors'])
    honors += [{'level': n, 'name': f'刷题传说 · {(n-60)//10+1}星'} for n in range(70, (lv//10+2)*10, 10)]
    title = state(g).get('equipped_honor') or next(h['name'] for h in reversed(honors) if h['level'] <= lv)
    future = next((h for h in honors if h['level'] > lv), None)
    return {'level': lv, 'xp': effective_xp(g), 'earned_xp': g['xp'], 'within': effective_xp(g)-threshold(lv),
            'required': required(lv), 'title': title, 'next_honor': future,
            'honors': [{**h, 'unlocked': lv >= h['level'] or h['level'] in state(g).get('honors',[])} for h in honors]}

def collect_honors(g):
    earned=state(g).setdefault('honors',[0])
    for milestone in range(10,level(g)+1,10):
        if milestone not in earned:earned.append(milestone)

def migrate(progress, *, fresh, old_level, old_fraction, now=None):
    import desktop_product as p
    g, s = progress['game'], p.state(progress['game'])
    if enabled(g):
        return s
    today = p.day_key(now)
    original = int(g.get('xp', 0))
    protected = threshold(old_level) + int(required(old_level)*old_fraction) if not fresh else original
    credit = max(0, protected-original)
    archive = copy.deepcopy(g.get('skill_state', {}))
    old_definitions = json.loads(store.resource_path('assets/skill_config.json').read_text(encoding='utf-8'))['definitions']
    refund = 0
    for skill in old_definitions:
        bought = max(0, int(archive.get('purchased', {}).get(skill['id'], 0)))
        unused = min(bought, max(0, 1+bought-int(archive.get('used', {}).get(skill['id'], 0))))
        refund += unused*skill['price']
    refund += max(0, int(archive.get('ink', 0))) * 30
    g['coins'] += refund
    s['growth'] = {'version': 1, 'migration_credit': credit, 'original_xp': original,
                   'original_level': old_level if not fresh else 0, 'old_skill_archive': archive,
                   'old_desktop_skill_definitions':copy.deepcopy(p.CONFIG['skills']),
                   'refund_coins': refund, 'skills': {}, 'loadout': [], 'equipped_honor': None,
                   'settled_through': today, 'last_seen_day': today, 'enrollment': {h:today for h in s['heroes']},
                   'streak': 0, 'best_streak': 0, 'streak_last_day': None, 'badges': [], 'honors':[0],
                   'xp_remainder': 0, 'arena_records': {}, 'transactions': {}}
    # 原始旧技能证据在归档；退款后不留下可再次消费的已购次数。
    g['skill_state'] = {'schema_version': 1, 'purchased': {}, 'used': {x['id']:1 for x in old_definitions}, 'queued': {}, 'ink':0}
    for a in [g.get('active'), progress.get('practice'), *g.get('paused', {}).values()]:
        if isinstance(a, dict) and not a.get('settled'):
            a.setdefault('ruleset', '5.1.0')
    s['version'] = 3
    s['migration'].update(to_version=3, growth_original_xp=original, growth_original_level=old_level,
                          growth_credit=credit, skill_refund=refund, acknowledged=fresh,
                          from_version=None if fresh else 2)
    p.refresh_capacity(g)
    return s

def enroll(g, hero):
    import desktop_product as p
    state(g)['enrollment'].setdefault(hero,max(p.day_key(),state(g)['last_seen_day']))

def day(g, now=None, key=None):
    import desktop_product as p
    key = key or max(p.day_key(now), state(g)['last_seen_day'])
    value = p.state(g)['daily'].setdefault(key, {'answers': {}, 'coins':0, 'consolidation_claimed':False, 'mood_cost':0})
    value.setdefault('active_qids', {})
    value.setdefault('xp_qids', {})
    return value

def login(progress, *, now=None):
    import desktop_product as p
    g, s = progress['game'], p.state(progress['game'])
    st = state(g)
    today = max(p.day_key(now), st['last_seen_day'])
    cursor, end = date.fromisoformat(st['settled_through']), date.fromisoformat(today)
    summary = {'days':0, 'points':0, 'heroes':{}, 'hero':p.hero_id(g)}
    # settled_through所指日期已豁免/已结算，其后直到昨天逐日结算。
    check = cursor + timedelta(days=1)
    while check < end:
        key = check.isoformat()
        qualified = len(day(g, key=key)['active_qids']) >= CONFIG['daily_target']
        if not qualified:
            summary['days'] += 1
            for hero_id, hero in s['heroes'].items():
                if st['enrollment'].get(hero_id, today) >= key:
                    continue
                loss = min(hero['energy'], CONFIG['missed_day_points']*100)
                hero['energy'] -= loss
                summary['heroes'][hero_id] = summary['heroes'].get(hero_id, 0)+loss/100
                summary['points'] += loss/100
        check += timedelta(days=1)
    if end > cursor:
        st['settled_through'] = (end-timedelta(days=1)).isoformat()
    st['last_seen_day'] = today
    s['last_active_day'] = today
    s['offline_summary'] = summary
    day(g, key=today)
    return summary

def activity(g, qid, key):
    st, d = state(g), day(g, key=key)
    d['active_qids'][qid] = True
    if len(d['active_qids']) >= CONFIG['daily_target'] and not d.get('qualified'):
        d['qualified'] = True
        previous = st['streak_last_day']
        st['streak'] = st['streak']+1 if previous and date.fromisoformat(key)-date.fromisoformat(previous) == timedelta(days=1) else 1
        st['streak_last_day'] = key
        st['best_streak'] = max(st['best_streak'], st['streak'])
        for n in (3,7,30):
            if st['streak'] >= n and n not in st['badges']:
                st['badges'].append(n)

def daily_view(g):
    key = state(g)['last_seen_day']
    count = len(day(g, key=key)['active_qids'])
    st = state(g)
    streak = st['streak']
    previous = st['streak_last_day']
    if previous and (date.fromisoformat(key)-date.fromisoformat(previous)).days > 1:
        streak = 0
    target=CONFIG['daily_target']
    return {'day':key, 'count':count, 'remaining':max(0,target-count), 'qualified':count>=target,
            'streak':streak, 'best_streak':st['best_streak'], 'badges':st['badges']}

def prepare(g, a):
    import finance
    a['ruleset'] = RULESET
    a['skill_snapshot'] = {key: state(g)['skills'][key] for key in state(g)['loadout']
                           if key in state(g)['skills'] and key in SKILLS and not passive(key)}
    a['companions_snapshot'] = finance.companion_ids(g)[:companion_limit(g)]
    a['bond_snapshot'] = {'rank': bond_rank(g), 'bonuses': bond_bonuses(g)}
    if a.get('product_mode') == 'arena':
        a['skill_snapshot'] = {}
    a.update(skill_uses={}, timers={}, primary_submissions={}, xp_earned=0,level_at_start=level(g))
    from desktop_challenge import freeze
    freeze(g,a)
    return a

def upgrade_attempt(g, a):
    """旧挑战保留成绩、草稿和已有截止，不能以旧ruleset绕过新版限制。"""
    if a.get('ruleset') and 'challenge_rules' not in a:
        from desktop_challenge import freeze
        freeze(g,a,legacy=True)
    if current(a):
        return a
    if not a.get('ruleset'):
        return prepare(g, a)
    a.setdefault('product_mode', 'adventure')
    a.setdefault('skill_snapshot', {})
    a.setdefault('skill_uses', {})
    a.setdefault('timers', {})
    a.setdefault('primary_submissions', {})
    a.setdefault('xp_earned', 0)
    a.setdefault('level_at_start', level(g))
    a['previous_ruleset'] = a.get('ruleset')
    a['ruleset'] = RULESET
    return a

def award(progress, question, a, *, correct=False, assisted=False, now=None, primary=False):
    import desktop_product as p
    g, qid = progress['game'], question['id']
    login(progress, now=now)
    key = a.get('primary_submissions', {}).get(qid, {}).get('day') or max(p.day_key(now), state(g)['last_seen_day'])
    d = day(g, key=key)
    activity(g, qid, key)
    credit = d['xp_qids'].setdefault(qid, {'completion':0, 'correct':0})
    weight = CONFIG['mode_weights'].get(a.get('product_mode'), 80)
    subjective = store.is_subjective(question)
    completed = CONFIG['question_xp']['subjective' if subjective else 'objective']*weight
    bonus = CONFIG['question_xp']['subjective_correct' if subjective else 'objective_correct']*weight if correct and not assisted else 0
    delta = max(0, completed-credit['completion']) + max(0, bonus-credit['correct'])
    credit['completion'], credit['correct'] = max(completed,credit['completion']), max(bonus,credit['correct'])
    numerator = delta*(100+int(a.get('bonuses', {}).get('xp',0))) + state(g)['xp_remainder']
    xp, state(g)['xp_remainder'] = divmod(numerator, 10000)
    g['xp'] += xp
    a['xp_earned'] += xp
    p.refresh_capacity(g)
    return xp

def base_seconds(g, question):
    subjective = store.is_subjective(question)
    rules = CONFIG['timer']
    return rules['subjective_seconds']+rules['subjective_per_level']*level(g) if subjective else rules['objective_seconds']+rules['objective_per_level']*level(g)

def start_timer(g, a, question, *, now=None):
    if not timed(a):
        return None
    import desktop_product as p
    p.require_action(g)
    qid = question['id']
    if qid not in a['qids'] or qid in a['answers'] or qid in a.get('primary_submissions', {}):
        return None
    now = time.time() if now is None else now
    timer = a['timers'].get(qid)
    if timer:
        return timer
    from desktop_challenge import duration as challenge_duration
    duration = challenge_duration(g,a,question)
    timer = {'started_at':now,'deadline':now+duration,'duration':duration,'extension':0,'status':'running','level':level(g)}
    a['timers'][qid] = timer
    return timer

def check_deadline(a, qid, *, now=None):
    if not timed(a):
        return
    t = a.get('timers', {}).get(qid)
    if not t:
        raise ValueError('题目尚未显示并开始计时，请稍候再提交或施法。')
    if t and t['status'] == 'running' and (time.time() if now is None else now) >= t['deadline']:
        raise ValueError('本题已超时，请等待自动记录并进入下一题。')

def mark_timer(a, qid, status):
    if qid in a.get('timers', {}):
        a['timers'][qid]['status'] = status

def submit_primary(progress, question, a, draft, *, now=None):
    import desktop_product as p
    qid = question['id']
    if qid in a['primary_submissions']:
        return a['primary_submissions'][qid]
    check_deadline(a,qid,now=now)
    if not str(draft).strip():
        raise ValueError('请先填写非空作答，再提交并对照参考答案。')
    login(progress,now=now)
    p.require_action(progress['game'])
    primary = {'draft':copy.deepcopy(draft),'day':state(progress['game'])['last_seen_day'],
               'submitted_at':time.time() if now is None else now,'xp':0,'hero':p.hero_id(progress['game'])}
    a['primary_submissions'][qid] = primary
    primary['xp'] = award(progress,question,a,now=now,primary=True)
    mark_timer(a,qid,'submitted')
    return primary

def case_text(question,snapshot):
    lines=[]
    for sub in question.get('subquestions',[]):
        text=snapshot.get('process',{}).get(sub['id'],'')
        if str(text).strip():lines.append(f"（{sub['id']}）{text}")
    for check in question.get('numeric_checks',[]):
        text=snapshot.get('values',{}).get(check['key'],'')
        if str(text).strip():
            unit=snapshot.get('units',{}).get(check['key'],'')
            lines.append(f"{check['label']}：{text} {unit}")
    return '\n'.join(lines)

def record_action(progress, question, correct, answer, a, *, mode, legacy, now=None, self_assessed=False, timeout=False):
    import desktop_product as p
    qid, g = question['id'], progress['game']
    if qid in a.get('product_actions', {}):
        return a['product_actions'][qid]
    login(progress,now=now)
    p.require_action(g)
    if not timeout:
        check_deadline(a,qid,now=now)
    # 复用已验收的体力、心情、金币、错题建材规则；经验由新规则单独结算。
    previous_xp, remainder = g['xp'], p.state(g)['reward_remainders']['xp']
    legacy_mode = 'arena' if mode=='arena_skills' else mode
    result = legacy(progress,question,correct,answer,a,mode=legacy_mode,
                    now=now,self_assessed=self_assessed)
    g['xp'], p.state(g)['reward_remainders']['xp'] = previous_xp, remainder
    result['xp'] = 0 if timeout else award(progress,question,a,correct=correct,assisted=result['assisted'],now=now)
    if qid in a.get('primary_submissions', {}):
        result['xp'] += a['primary_submissions'][qid]['xp']
    rank = a.get('skill_snapshot', {}).get('mercy',0)
    hero = p.active_hero(g)
    cost = mana_cost(a, 'mercy')
    protected = bool(not correct and rank and mode != 'arena' and hero['energy'] > 0 and hero['mana'] >= cost)
    if protected:
        hero['mana'] -= cost
        a['skill_uses']['mercy'] = a['skill_uses'].get('mercy', 0) + 1
        a.setdefault('skill_targets', []).append('mercy:' + qid)
    result.update(game_correct=bool(correct or protected),protected=protected,timeout=timeout)
    key = a.get('primary_submissions', {}).get(qid, {}).get('day') or state(g)['last_seen_day']
    result['mana_restored'] = 0 if timeout else restore_correct_mana(g, question, a, correct=correct, assisted=result['assisted'], key=key)
    result['mana_spent'] = cost if protected else 0
    mark_timer(a,qid,'timeout' if timeout else 'graded')
    p.refresh_capacity(g)
    return result

def stamp_answer(a, qid):
    record, result = a['answers'][qid], a['product_actions'][qid]
    record.update(game_correct=result['game_correct'],protected=result['protected'],timeout=result['timeout'])
    return record

def timeout(progress, question, a, draft='', *, now=None):
    import desktop_product as p
    qid = question['id']
    if qid in a['answers']:
        return a['answers'][qid]
    p.require_action(progress['game'])
    if not timed(a):
        raise ValueError('学习与错题练习不限时，不会自动超时。')
    if qid in a.get('primary_submissions', {}):
        raise ValueError('本题已经提交，等待对照自评，不会超时。')
    t = a.get('timers', {}).get(qid)
    if not t or (time.time() if now is None else now) < t['deadline']:
        raise ValueError('本题尚未到截止时间。')
    a['drafts'][qid] = copy.deepcopy(draft)
    reward = record_action(progress,question,False,str(draft),a,mode=a['product_mode'],legacy=p._legacy_record_action,
                           now=now,self_assessed=store.is_subjective(question),timeout=True)
    a['answers'][qid] = {'correct':False,'user_answer':str(draft),'ts':time.time() if now is None else now,
                         'assisted':reward['assisted'],'self_assessed':store.is_subjective(question)}
    return stamp_answer(a,qid)

def skill_view(g):
    lv, st = level(g), state(g)
    rows = []
    for s in CONFIG['skills']:
        rank = st['skills'].get(s['id'],0)
        needed = s['level']+rank*10
        price = s['price']*(2**rank)
        rows.append({**s,'rank':rank,'required_level':needed,'next_price':price,'maxed':rank==4,
                     'allowed':rank<4 and lv>=needed and g['coins']>=price,
                      'equipped':not passive(s['id']) and s['id'] in st['loadout']})
    return rows

def learn(progress, skill_id, operation_id):
    g, st = progress['game'], state(progress['game'])
    prior = st['transactions'].get(operation_id)
    if prior:
        if prior['skill_id'] != skill_id:
            raise ValueError('交易编号与技能不一致。')
        return prior
    s = next((s for s in skill_view(g) if s['id']==skill_id),None)
    if not s or not s['allowed']:
        raise ValueError('尚未达到升级等级、金币不足或技能已满阶。')
    g['coins'] -= s['next_price']
    st['skills'][skill_id] = s['rank']+1
    if not passive(skill_id) and len(st['loadout']) < 3 and skill_id not in st['loadout']:
        st['loadout'].append(skill_id)
    result = {'skill_id':skill_id,'rank':s['rank']+1,'coins':s['next_price']}
    st['transactions'][operation_id] = result
    if passive(skill_id):
        import desktop_product as p
        p.refresh_capacity(g)
    return result

def equip(progress, skill_id):
    st = state(progress['game'])
    if passive(skill_id):
        raise ValueError('精灵羁绊为被动技能，精灵同行时自动生效，不占主动技能位置。')
    if skill_id not in st['skills']:
        raise ValueError('请先学习这项技能。')
    if skill_id in st['loadout']:
        st['loadout'].remove(skill_id)
    elif len(st['loadout']) >= 3:
        raise ValueError('每场最多携带三项技能，请先卸下一项。')
    else:
        st['loadout'].append(skill_id)

_AUXILIARY = None
def auxiliary(question, skill_id):
    global _AUXILIARY
    if _AUXILIARY is None:
        path = store.resource_path('assets/learning_hints.json')
        _AUXILIARY = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    value = _AUXILIARY.get(question['id'], {})
    return value.get('outline' if skill_id=='outline' else 'memory',[])

def skill_status(g, a, question, skill_id, *, now=None):
    if passive(skill_id):
        return {'allowed':False,'reason':'精灵羁绊为被动技能，无需施法','cost':0}
    if a.get('kind') in ('hero_trial','spirit_hunt'):
        return {'allowed':False,'reason':'收服挑战禁用辅助技能','cost':0}
    import desktop_product as p
    rank = a.get('skill_snapshot', {}).get(skill_id,0)
    cost = mana_cost(a, skill_id)
    mana = p.active_hero(g)['mana'] if p.state(g)['starter_claimed'] else 0
    reason = ''
    qid = question['id']
    if not rank:
        reason = '本场未携带'
    elif p.death_locked(g):
        reason = '零体力，请还魂或重开'
    elif a.get('product_mode')=='arena':
        reason = '普通比武禁用技能'
    elif qid in a['answers'] or qid in a.get('primary_submissions', {}):
        reason = '本题已提交'
    elif f'{skill_id}:{qid}' in a.get('skill_targets',[]):
        reason = '本题已使用'
    elif skill_id == 'clock' and not timed(a):
        reason = '不限时学习无需延时'
    elif timed(a) and qid not in a.get('timers', {}):
        reason = '本题尚未开始计时'
    elif timed(a) and a['timers'][qid]['status'] == 'running' and (time.time() if now is None else now) >= a['timers'][qid]['deadline']:
        reason = '本题已超时'
    elif mana < cost:
        reason = '魔法不足'
    elif skill_id in ('memory','outline') and not auxiliary(question,skill_id):
        reason = '本题暂无可靠线索'
    elif skill_id=='outline' and not store.is_subjective(question):
        reason = '只适用于主观题'
    elif skill_id=='insight' and (question.get('type')!='单选题' or len(question.get('options',{}))<3):
        reason = '只适用于至少三个选项的单选题'
    return {'rank':rank,'cost':cost,'mana':mana,'reason':reason,'allowed':not reason}

def use(progress, a, question, skill_id, *, now=None):
    import desktop_product as p
    p.require_action(progress['game'])
    if question['id'] not in a['qids'] or a.get('settled'):
        raise ValueError('请在当前场次的未提交题目上施法。')
    check_deadline(a,question['id'],now=now)
    status = skill_status(progress['game'],a,question,skill_id,now=now)
    if not status['allowed'] or skill_id=='mercy':
        raise ValueError(status['reason'] or '瞒天过海在错误时自动施展。')
    rank, qid = status['rank'], question['id']
    result = {}
    if skill_id=='clock':
        seconds = SKILLS['clock']['subjective' if store.is_subjective(question) else 'objective'][rank-1]
        a['timers'][qid]['deadline'] += seconds
        a['timers'][qid]['duration'] += seconds
        a['timers'][qid]['extension'] += seconds
        result = {'seconds':seconds}
    elif skill_id=='insight':
        options = question.get('options',{})
        if isinstance(options,list):
            options = {chr(65+i):s for i,s in enumerate(options)}
        answer = str(question['answer']).strip().upper()
        if answer not in options:
            raise ValueError('本题答案格式暂不适合排除提示。')
        wrong = sorted(key for key in options if key != answer)
        count = min(SKILLS['insight']['exclude'][rank-1],len(options)-2)
        a.setdefault('hints', {})[qid] = wrong[:count]
        result = {'excluded':wrong[:count]}
    else:
        lines = auxiliary(question,skill_id)
        if isinstance(lines,str):
            lines = [lines]
        lines = lines[:SKILLS['outline']['lines'][rank-1]] if skill_id=='outline' else lines[:1]
        a.setdefault('growth_clues', {})[qid] = lines
        result = {'lines':lines}
    if skill_id!='clock':
        if qid not in a.setdefault('assisted_qids',[]):
            a['assisted_qids'].append(qid)
    a.setdefault('skill_targets',[]).append(f'{skill_id}:{qid}')
    a['skill_uses'][skill_id] = a['skill_uses'].get(skill_id,0)+1
    p.active_hero(progress['game'])['mana'] -= status['cost']
    result.update(mana_spent=status['cost'], npc_id=SKILLS[skill_id]['npc_id'])
    return result

def equip_honor(progress, name):
    if not any(h['name']==name and h['unlocked'] for h in view(progress['game'])['honors']):
        raise ValueError('尚未获得这个称号。')
    state(progress['game'])['equipped_honor'] = name

def finish(progress, a, result):
    import desktop_product as p
    raw = sum(bool(r['correct']) for r in a['answers'].values())
    game_correct = sum(bool(r.get('game_correct',r['correct'])) for r in a['answers'].values())
    result.update(correct=raw,game_correct=game_correct,wrong_qids=[qid for qid,r in a['answers'].items() if not r['correct']],
                  assisted=any(r.get('assisted') or r.get('protected') for r in a['answers'].values()),
                  protected_qids=[qid for qid,r in a['answers'].items() if r.get('protected')],
                  timeout_qids=[qid for qid,r in a['answers'].items() if r.get('timeout')],
                  answer_xp=a.get('xp_earned',0),settlement_xp=result['xp'])
    result['xp'] += a.get('xp_earned',0)
    result['level_before']=a.get('level_at_start',result.get('level_before',level(progress['game'])))
    result['level_after']=level(progress['game'])
    result['growth'] = view(progress['game'])
    if 'companions_snapshot' in a:
        result['companions_snapshot'] = list(a['companions_snapshot'])
    if a['product_mode'] in ('arena','arena_skills'):
        records = state(progress['game'])['arena_records'].setdefault(a['product_mode'], {'胜':0,'平':0,'败':0})
        records[result['outcome']] += 1
    p.refresh_capacity(progress['game'])
    return result

def settle_classic(progress, *, legacy, rng=None, surprise_rng=None):
    """原经营剧情的新场次也使用统一经验、80%通关与真实成绩。"""
    import desktop_product as p
    import game
    g,a=progress['game'],progress['game']['active']
    if a['settled']:return a['result']
    p.require_action(g)
    if any(qid not in a['answers'] for qid in a['qids']):raise ValueError('请完成全部题目后结算。')
    before_xp,before_badges=g['xp'],set(g['badges'])
    before_ink=g.get('skill_state',{}).get('ink',0)
    raw={qid:r['correct'] for qid,r in a['answers'].items()}
    previous=copy.deepcopy(g['results'].get(a['stage_id'],{}))
    threshold_before=game.CONFIG['pass_percent']
    try:
        game.CONFIG['pass_percent']=80
        for r in a['answers'].values():r['correct']=r.get('game_correct',r['correct'])
        result=legacy(progress,rng=rng,surprise_rng=surprise_rng)
    finally:
        game.CONFIG['pass_percent']=threshold_before
        for qid,correct in raw.items():a['answers'][qid]['correct']=correct
    g['xp']=before_xp
    points=20 if result['first_clear'] else 0
    points+=50*len(set(g['badges'])-before_badges)
    result['xp']=p._reward_with_bonus(g,points,'xp',a['bonuses'])
    g['xp']+=result['xp']
    aided=any(r.get('assisted') or r.get('protected') for r in a['answers'].values())
    self_assessed=any(r.get('self_assessed') for r in a['answers'].values())
    if result['passed']:
        result['stars']=1 if self_assessed else 3 if result['correct']==result['total'] and not aided else 2
    result.update(assisted=aided,skill_name='技能助力' if aided else '',new_skills=[],pass_percent=80)
    if aided:result['quality']='技能助力'
    if result['passed']:
        saved=g['results'][a['stage_id']]
        saved.update(best_correct=max(previous.get('best_correct',0),sum(raw.values())),
            best_game_correct=sum(r.get('game_correct',r['correct']) for r in a['answers'].values()),
            best_stars=max(previous.get('best_stars',0),result['stars']),assisted=aided or previous.get('assisted',False))
    # 已退役的随机墨水兑换为30金币，避免新场再生成无法使用的旧耗材。
    ink=max(0,g.get('skill_state',{}).get('ink',0)-before_ink)
    if ink:
        g['skill_state']['ink']=before_ink;g['coins']+=ink*30;result['coins']+=ink*30
        for item in result.get('growth',[]):
            if item.get('kind')=='ink':item.update(name='惊喜金币',coins=30,kind='coins')
    if result.get('loot') and result['loot'].get('xp'):
        result['loot']['xp']=0
        result['loot']['name']='成长纪念宝箱 · 基础成长奖励已计入本轮'
    surprises=result.get('growth',[])
    finish(progress,a,result)
    result['growth']=surprises
    return result
