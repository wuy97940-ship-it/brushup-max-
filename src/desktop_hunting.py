"""5.4收服规则。只修改调用者候选存档，保存成功后才允许演出。"""
from __future__ import annotations
import copy
import json
import math
import random
import time
import uuid
import store

CONFIG=json.loads(store.resource_path('assets/hunting_config.json').read_text(encoding='utf-8'))
SPIRITS={s['id']:s for s in CONFIG['spirits']}
ULTIMATES=json.loads(store.resource_path('assets/hunting_ultimates580.json').read_text(encoding='utf-8'))

def ultimate_for(kind,target):
    definition=ULTIMATES['targets'].get(target)
    tier='hero' if kind=='hero_trial' else SPIRITS.get(target,{}).get('rarity')
    if not definition or tier not in ULTIMATES['tiers']:return None
    return {**copy.deepcopy(ULTIMATES['tiers'][tier]),**definition,'tier':tier,
            'projectile':definition.get('projectile',SPIRITS.get(target,{}).get('projectile','question')),
            'minimum_seconds':ULTIMATES['minimum_seconds']}

def state(g):
    return g['product'].setdefault('hunting',{'version':1,'active':None,'hero_qualifications':{},'history':[],'last_result':None})

def initialize(g):
    s=state(g)
    if s.get('version')!=1:raise ValueError('猎场存档版本暂不支持，请保留原档。')
    for key,value in {'active':None,'hero_qualifications':{},'history':[],'last_result':None}.items():
        s.setdefault(key,copy.deepcopy(value))
    return s

def active(g):return g.get('product',{}).get('hunting',{}).get('active')

def guard(g):
    if active(g):raise ValueError('收服挑战尚未结束，请返回精灵狩猎继续，或主动放弃。')

def eligible(g,qmap):
    ids=set()
    for campaign in (g.get('campaign',{}),g.get('product_campaign',{})):
        for sid,item in campaign.get('levels',{}).items():
            if g.get('results',{}).get(sid,{}).get('cleared'):
                ids.update(q for q in item.get('qids',[]) if q in qmap and not store.is_subjective(qmap[q]))
    return sorted(ids)

def question_pool(progress,qmap,count,rng):
    pool=eligible(progress['game'],qmap)
    if len(pool)<count:raise ValueError(f'需要先通关{count}道不同客观题，目前只有{len(pool)}道。')
    wrong=set(progress.get('wrong_book',[]));tie={q:rng.random() for q in pool}
    pool.sort(key=lambda q:(q not in wrong,progress.get('answered',{}).get(q,{}).get('ts',0),tie[q]))
    chosen=pool[:count];rng.shuffle(chosen)
    return chosen

def _prior(g,token,op,target=None):
    import desktop_product as p
    if not token or not isinstance(token,str):raise ValueError('缺少有效操作编号。')
    prior=p.state(g)['transactions'].get(token)
    if prior:
        if prior['operation']!=op or prior.get('item')!=target:raise ValueError('操作编号与当前收服操作不一致。')
        return copy.deepcopy(prior['result'])

def _receipt(g,token,op,target,result):
    import desktop_product as p
    p.state(g)['transactions'][token]={'operation':op,'item':target,'result':copy.deepcopy(result)}
    return result

def _flow(a,**kw):
    return {'flow':'hunting','attempt_id':a['id'],'kind':a['kind'],'target':a['target'],'phase':a['phase'],**kw}

def _new(progress,qmap,kind,target,rules,token,biome,rng):
    import desktop_product as p
    import desktop_growth as growth
    g=progress['game'];p.login(progress);p.require_action(g);guard(g)
    if biome not in ('forest','island','stars'):raise ValueError('请选择森林、海岛或星空猎场。')
    qids=question_pool(progress,qmap,rules['questions'],rng)
    if kind=='hero_trial':
        if target not in p.HEROES or target in p.state(g)['heroes']:raise ValueError('只能挑战尚未解锁的主角。')
        if target in state(g)['hero_qualifications']:raise ValueError('已通过考试，请支付尾款。')
        if g['coins']<rules['deposit']:raise ValueError(f"定金需要{rules['deposit']}金币。")
        g['coins']-=rules['deposit']
    a={'id':uuid.uuid4().hex,'kind':kind,'target':target,'hero':p.hero_id(g),'phase':'running',
       'qids':qids,'answers':{},'drafts':{},'references':[],'index':0,'settled':False,'result':None,
       'bonuses':p.bonuses(g),'product_mode':kind,'biome':biome,'rules_snapshot':copy.deepcopy(rules),
       'start_token':token,'started_at':time.time()}
    growth.prepare(g,a);a['skill_snapshot']={}
    a['ultimate_snapshot']=ultimate_for(kind,target)
    a['ultimates']={}
    a['ultimate_energy_cap']=p.state(g)['heroes'][a['hero']]['energy']*ULTIMATES['energy_cap_percent']//100
    a['rules_snapshot'].update(hero_base_seconds=growth.CONFIG['timer']['objective_seconds'],hero_per_level=growth.CONFIG['timer']['objective_per_level'],hero_level=p.level(g))
    state(g)['active']=a
    return a

def start_hero(progress,qmap,target,token,*,biome='forest',rng=None):
    prior=_prior(progress['game'],token,'hunt_hero_start',target)
    if prior:return prior
    a=_new(progress,qmap,'hero_trial',target,CONFIG['hero_trial'],token,biome,rng or random.SystemRandom())
    return _receipt(progress['game'],token,'hunt_hero_start',target,_flow(a,operation='start',deposit=a['rules_snapshot']['deposit']))

def start_spirit(progress,qmap,token,*,biome='forest',rng=None):
    import desktop_product as p
    g=progress['game'];prior=_prior(g,token,'hunt_spirit_start')
    if prior:return prior
    p.login(progress);p.require_action(g);guard(g)
    if len(eligible(g,qmap))<CONFIG['spirit_unlock_questions']:raise ValueError(f"先通关{CONFIG['spirit_unlock_questions']}道不同客观题，再进入精灵狩猎。")
    rng=rng or random.SystemRandom()
    groups={r:[s for s in SPIRITS.values() if s['rarity']==r and s['id'] not in g['inventory']] for r in CONFIG['rarities']}
    remaining=[r for r,pool in groups.items() if pool]
    if not remaining:raise ValueError(f'{len(SPIRITS)}只精灵已全部收服，图鉴已完成。')
    draw=rng.random()*sum(CONFIG['rarities'][r]['weight'] for r in remaining);chosen=remaining[-1]
    for rarity in remaining:
        draw-=CONFIG['rarities'][rarity]['weight']
        if draw<0:chosen=rarity;break
    target=rng.choice(groups[chosen])['id']
    tier=CONFIG['rarities'][chosen]
    rules={**tier,'pass_percent':tier.get('pass_percent',CONFIG['spirit_pass_percent']),'rarity':chosen}
    a=_new(progress,qmap,'spirit_hunt',target,rules,token,biome,rng)
    return _receipt(g,token,'hunt_spirit_start',None,_flow(a,operation='start'))

def _attempt(g,identifier=None):
    a=active(g)
    if not a or identifier is not None and a['id']!=identifier:raise ValueError('收服场次已改变，请返回猎场查看。')
    return a

def start_timer(progress,qid,attempt_id,*,now=None,rng=None):
    import desktop_product as p
    g=progress['game'];a=_attempt(g,attempt_id);p.require_action(g)
    if a['phase']!='running' or qid!=a['qids'][a['index']]:raise ValueError('当前不能展示这道题。')
    if qid not in a['answers'] and qid not in a['timers']:
        moment=time.time() if now is None else now;r=a['rules_snapshot']
        seconds=r['seconds'] if a['kind']=='spirit_hunt' else r['hero_base_seconds']+r['hero_per_level']*r['hero_level']
        skill=a.get('ultimate_snapshot');hit={'triggered':False}
        if skill:
            randomizer=rng or random.SystemRandom();roll=randomizer.random()
            hit.update(roll=roll,skill=skill['name'],power=skill['power'],color=skill['color'],projectile=skill['projectile'])
            if roll<skill['chance']:
                hero=p.state(g)['heroes'][a['hero']]
                options=['time']
                spent=sum(int(x.get('energy_spent',0)) for x in a.get('ultimates',{}).values())
                remaining=max(0,a.get('ultimate_energy_cap',0)-spent)
                if remaining and hero['energy']>0:options.append('energy')
                if hero['mana_maximum']>0 and hero['mana']>0:options.append('mana')
                kind=randomizer.choice(options);hit.update(triggered=True,effect=kind,energy_spent=0,mana_spent=0,time_spent=0)
                if kind=='energy':
                    amount=min(int(round(skill['energy_points']*100)),remaining,hero['energy'])
                    hero['energy']-=amount;hit['energy_spent']=amount
                    if hero['energy']<=0:p.state(g)['death_lock']=a['hero']
                elif kind=='mana':
                    amount=min(skill['mana_points'],hero['mana']);hero['mana']-=amount;hit['mana_spent']=amount
                else:
                    hit['time_spent']=min(skill['time_seconds'],max(0,seconds-skill['minimum_seconds']))
                    seconds-=hit['time_spent']
        a.setdefault('ultimates',{})[qid]=hit
        # 招式演出在答题时钟之前；重开、重试沿用已保存的截止时间。
        presentation=0 if not hit['triggered'] or p.state(g)['settings'].get('reduced_motion') else .6
        a['timers'][qid]={'started_at':moment+presentation,'deadline':moment+presentation+seconds,'duration':seconds,'status':'running','extension':0,'level':p.level(g)}
        if p.death_locked(g):
            return _fail(g,a,'受到大招打击，体力耗尽',ultimate=hit)
    return _flow(a,operation='timer',ultimate=copy.deepcopy(a.get('ultimates',{}).get(qid,{'triggered':False})))

def _archive(g,a,result):
    s=state(g);a.update(result=result,settled=True)
    s['history'].append(copy.deepcopy(a));s['history']=s['history'][-30:]
    s['last_result']=copy.deepcopy(result);s['active']=None
    return result

def _fail(g,a,reason,*,ultimate=None):
    import desktop_product as p
    hero=p.state(g)['heroes'][a['hero']]
    amount=a['rules_snapshot'].get('failure_points',0)*100 if a['kind']=='spirit_hunt' else 0
    spent=min(hero['energy'],amount);hero['energy']-=spent
    if hero['energy']<=0:p.state(g)['death_lock']=a['hero']
    a['phase']='failed'
    result=_flow(a,operation='finish',passed=False,reason=reason,correct=sum(r['correct'] for r in a['answers'].values()),total=len(a['qids']),
                 answered=len(a['answers']),failure_energy=spent/100,wrong_qids=[q for q,r in a['answers'].items() if not r['correct']])
    if ultimate is not None:result['ultimate']=copy.deepcopy(ultimate)
    return _archive(g,a,result)

def fail_if_dead(progress):
    import desktop_product as p
    g=progress['game'];a=active(g)
    return _fail(g,a,'体力耗尽，挑战结束') if a and p.death_locked(g) else None

def submit(progress,question,answer,attempt_id,*,now=None,timeout=False):
    import desktop_product as p
    import desktop_growth as growth
    from app import is_correct
    g=progress['game'];qid=question['id']
    a=active(g)
    if not a or a['id']!=attempt_id:
        previous=next((x for x in reversed(state(g)['history']) if x['id']==attempt_id),None)
        if previous and qid in previous['answers']:return copy.deepcopy(previous['result'])
        raise ValueError('收服场次已改变，请返回猎场查看。')
    if qid in a['answers']:return _flow(a,operation='answer',qid=qid)
    if a['phase']!='running' or qid!=a['qids'][a['index']] or store.is_subjective(question):raise ValueError('请依次回答当前客观题。')
    if p.hero_id(g)!=a['hero']:raise ValueError('挑战期间不能切换出战主角。')
    p.login(progress,now=now)
    if p.death_locked(g):return _fail(g,a,'体力耗尽，挑战结束')
    t=a['timers'].get(qid);moment=time.time() if now is None else now
    if not t:raise ValueError('题目尚未显示并开始计时。')
    expired=moment>=t['deadline']
    if timeout and not expired:raise ValueError('当前题尚未超时。')
    timeout=bool(expired)
    if not timeout and not str(answer).strip():raise ValueError('请先作答。')
    correct=not timeout and is_correct(question,str(answer))
    before_xp,rem=g['xp'],p.state(g)['reward_remainders']['xp']
    energy=None if a['kind']=='hero_trial' else (0 if correct else a['rules_snapshot']['wrong_points'])
    reward=p._legacy_record_action(progress,question,correct,str(answer),a,mode=a['kind'],now=now,
                                  energy_points=energy,suppress_mood=a['kind']=='spirit_hunt')
    g['xp']=before_xp;p.state(g)['reward_remainders']['xp']=rem
    reward['xp']=0 if timeout else growth.award(progress,question,a,correct=correct,assisted=False,now=now)
    reward.update(game_correct=correct,protected=False,timeout=timeout,mana_spent=0)
    reward['mana_restored']=0 if timeout else growth.restore_correct_mana(g,question,a,correct=correct,assisted=False,key=growth.state(g)['last_seen_day'])
    a['answers'][qid]={'correct':correct,'game_correct':correct,'user_answer':str(answer),'ts':moment,'assisted':False,'self_assessed':False,'timeout':timeout,'protected':False}
    t['status']='timeout' if timeout else 'graded';p.refresh_capacity(g)
    if p.active_hero(g)['energy']<=0:return _fail(g,a,'体力耗尽，挑战结束')
    right=sum(r['correct'] for r in a['answers'].values());left=len(a['qids'])-len(a['answers'])
    required=math.ceil(len(a['qids'])*a['rules_snapshot']['pass_percent']/100)
    if right+left<required:return _fail(g,a,'正确题数已无法达到通过标准')
    if not left:
        if a['kind']=='hero_trial':
            a['phase']='awaiting_payment'
            result=_flow(a,operation='finish',passed=True,correct=right,total=len(a['qids']),balance=a['rules_snapshot']['balance'],wrong_qids=[q for q,r in a['answers'].items() if not r['correct']])
            state(g)['hero_qualifications'][a['target']]={'attempt_id':a['id'],'balance':a['rules_snapshot']['balance'],'passed_at':moment,'result':copy.deepcopy(result)}
            return _archive(g,a,result)
        a['phase']='ready_to_throw'
        return _flow(a,operation='ready_to_throw',passed=True,correct=right,total=len(a['qids']))
    return _flow(a,operation='answer',qid=qid,timeout=timeout)

def advance(progress,attempt_id):
    a=_attempt(progress['game'],attempt_id)
    if a['phase']!='running' or a['qids'][a['index']] not in a['answers']:raise ValueError('请先提交当前题。')
    if a['index']>=len(a['qids'])-1:raise ValueError('挑战已完成。')
    a['index']+=1
    return _flow(a,operation='advance')

def abandon(progress,attempt_id,token):
    g=progress['game'];prior=_prior(g,token,'hunt_abandon',attempt_id)
    if prior:return prior
    result=_fail(g,_attempt(g,attempt_id),'主动放弃本次收服挑战')
    return _receipt(g,token,'hunt_abandon',attempt_id,result)

def throw_ball(progress,attempt_id,token,*,rng=None):
    import desktop_product as p
    g=progress['game'];prior=_prior(g,token,'hunt_throw',attempt_id)
    if prior:return prior
    a=_attempt(g,attempt_id);p.login(progress)
    if p.death_locked(g):return _receipt(g,token,'hunt_throw',attempt_id,_fail(g,a,'体力耗尽，精灵离开了'))
    p.require_action(g)
    if a['kind']!='spirit_hunt' or a['phase']!='ready_to_throw':raise ValueError('请先通过精灵答题挑战。')
    roll=(rng or random.SystemRandom()).random();a['capture_roll']=roll
    if roll>=a['rules_snapshot']['capture_percent']/100:result=_fail(g,a,'圆宝球没有收服精灵，它逃走了')
    else:
        a['phase']='captured'
        if a['target'] not in g['inventory']:g['inventory'].append(a['target'])
        result=_flow(a,operation='capture',passed=True,correct=sum(r['correct'] for r in a['answers'].values()),total=len(a['qids']),reason='收服成功',wrong_qids=[q for q,r in a['answers'].items() if not r['correct']])
        result=_archive(g,a,result)
    return _receipt(g,token,'hunt_throw',attempt_id,result)

def pay_balance(progress,target,token):
    import desktop_product as p
    import desktop_growth as growth
    g=progress['game'];prior=_prior(g,token,'hunt_balance',target)
    if prior:return prior
    p.login(progress);p.require_action(g);guard(g)
    qualification=state(g)['hero_qualifications'].get(target)
    if target in p.state(g)['heroes'] or not qualification:raise ValueError('请先通过该主角的100题考试。')
    balance=qualification['balance']
    if g['coins']<balance:raise ValueError(f'尾款需要{balance}金币，资格已保留，请继续学习。')
    g['coins']-=balance;s=p.state(g);archived=s['archived_heroes'].pop(target,None)
    s['heroes'][target]=archived['state'] if archived else p._new_hero(g)
    s['appearances'][target]=archived['appearance'] if archived else p._appearance(target)
    if target not in g['inventory']:g['inventory'].append(target)
    s['entitlements'][target]={'source':'hero_trial','attempt_id':qualification['attempt_id'],'transaction_id':token}
    growth.enroll(g,target);p.refresh_capacity(g);del state(g)['hero_qualifications'][target]
    result={'flow':'hunting','operation':'balance','kind':'hero_trial','target':target,'phase':'captured','passed':True,'price':balance,'attempt_id':qualification['attempt_id'],'reason':'主角已加入角色馆'}
    state(g)['last_result']=copy.deepcopy(result)
    return _receipt(g,token,'hunt_balance',target,result)

def equip_spirit(progress,target,*,replace=None):
    import desktop_product as p
    import finance
    g=progress['game']
    if target not in SPIRITS or target not in g['inventory']:raise ValueError('请先收服这只精灵。')
    p.require_action(g);guard(g)
    from desktop_growth import companion_limit
    limit=companion_limit(g)
    ids=[identifier for identifier in finance.companion_ids(g)
         if identifier in SPIRITS and identifier in g['inventory']][:limit]
    if replace is not None and (replace not in ids or target in ids):
        raise ValueError('请选择当前同行的一只进行替换。')
    if target in ids:
        ids.remove(target)
    elif replace is not None:
        ids[ids.index(replace)]=target
    elif limit==1:
        ids=[target]
    elif len(ids)<limit:
        ids.append(target)
    else:
        raise ValueError('两个同行名额已满，请选择要替换的精灵。')
    finance.set_companions(g,ids)
    p.refresh_capacity(g)
    return {'flow':'roles','operation':'companion','target':target,'companions':ids[:],'limit':limit}
