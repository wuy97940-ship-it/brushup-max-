"""5.5 challenge eligibility and immutable per-attempt rules."""
from __future__ import annotations
from functools import lru_cache
import copy
import store

def rank(question):
    return int(question.get('challenge_difficulty',question.get('difficulty',2)))

def arena_eligible(question):
    return (not store.is_subjective(question) and question.get('_status','published')=='published'
            and rank(question)>=4 and question.get('arena_eligible',False))

_installed_questions = None

def install_question_map(questions):
    global _installed_questions
    _installed_questions = {q['id']:q for q in questions}
    question_map.cache_clear()

@lru_cache(maxsize=1)
def question_map():return _installed_questions if _installed_questions is not None else {q['id']:q for q in store.load_questions()}

def arena_pool(questions,world):
    prefixes={'accounting':'acc_original_v01','finance':'cg_original_v02','law':'law_original_v01'}
    prefix=prefixes[world]
    return sorted((q for q in questions if q.get('book_id','').startswith(prefix) and arena_eligible(q)),
                  key=lambda q:(not q.get('verified_exam',False),-rank(q),q['id']))

def validate_arena(qids):
    qmap=question_map()
    if len(qids)<5 or len(set(qids))!=len(qids):raise ValueError('比武至少需要5道不同重难点题。')
    if any(qid not in qmap or not arena_eligible(qmap[qid]) for qid in qids):
        raise ValueError('比武只接受经核验的重难点客观题，不能加入常规题。')
    prefixes=('acc_original_v01','cg_original_v02','law_original_v01')
    worlds={next((prefix for prefix in prefixes if str(qmap[qid].get('book_id','')).startswith(prefix)),None) for qid in qids}
    if None in worlds:raise ValueError('比武只接受已核验的CPA学科题库。')
    if len(worlds)!=1:raise ValueError('比武题目须属于同一学科。')

def freeze(g,a,*,legacy=False):
    if 'challenge_rules' in a:return a['challenge_rules']
    import desktop_product as p
    import desktop_growth as growth
    item=g.get('product_campaign',{}).get('levels',{}).get(a.get('stage_id'),{})
    boss=item.get('kind')=='boss' and not item.get('subjective')
    b=p.CONFIG['boss'];e=p.CONFIG['energy'];reward=p.CONFIG['rewards']
    rules={'version':'5.4.1' if legacy else p.CONFIG['version'],'boss':boss,'level':a.get('level_at_start',p.level(g)),
           'answer_points':e['answer_points'],'wrong_points':0 if legacy else e['boss_wrong_points' if boss else 'wrong_points'],
           'pass_percent':80 if legacy else b['pass_percent'] if boss else p.CONFIG['pass_percent'],
           'first_stage_xp':20 if legacy else b['first_stage_xp'] if boss else reward['first_stage_xp'],
           'first_stage_coins':10 if legacy else b['first_stage_coins'] if boss else reward['first_stage_coins'],
           'mana_restore':3 if legacy else growth.CONFIG['mana']['correct_restore'],
           'skill_costs':{key:list(s.get('mana_costs',[])) for key,s in growth.SKILLS.items()},
           'objective_seconds':60,'objective_per_level':1,'subjective_seconds':480,'subjective_per_level':10}
    if boss and not legacy:rules.update({k:b[k] for k in ('objective_seconds','objective_per_level','objective_ceiling')})
    a['challenge_rules']=copy.deepcopy(rules)
    return a['challenge_rules']

def duration(g,a,q):
    rules=freeze(g,a)
    kind='subjective' if store.is_subjective(q) else 'objective'
    import desktop_product as p
    level=rules['level'] if rules['boss'] and rules['version'] != '5.4.1' else p.level(g)
    value=rules[kind+'_seconds']+rules[kind+'_per_level']*level
    return min(value,rules.get(kind+'_ceiling',value))
