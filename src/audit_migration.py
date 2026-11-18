"""Append audit to SHA-frozen shipped maps without regrouping saved levels."""
from __future__ import annotations
import copy,json
from functools import lru_cache
import store

@lru_cache(maxsize=1)
def config():
    return json.loads(store.resource_path('assets/audit_migration.json').read_text('utf-8'))

def extension(base,installed):
    audit=next((w for w in installed['worlds'] if w['id']=='audit'),None)
    if not audit:return copy.deepcopy(base)
    result=copy.deepcopy(base)
    if any(w['id']=='audit' for w in result['worlds']):raise ValueError('审计地图已存在，不能重复追加。')
    result['worlds'].append(copy.deepcopy(audit))
    added={sid:copy.deepcopy(s) for sid,s in installed['levels'].items() if s['world_id']=='audit'}
    if set(added)&set(result['levels']):raise ValueError('审计关卡编号与旧地图冲突。')
    result['levels'].update(added)
    result['bank_fingerprint']=installed['bank_fingerprint']
    return result

def classic(progress,installed):
    old=progress['game']['campaign']
    if not any(w['id']=='audit' for w in installed['worlds']):return False
    base=config()['trusted_550']['classic']
    if old!=base:return False
    saved_product=progress['game'].get('product_campaign')
    if saved_product and saved_product.get('version')==3 and saved_product not in config()['trusted_550']['products']:
        raise ValueError('产品地图与受信5.5.0基线不一致，原档保留，拒绝自动改写。')
    expanded=extension(base,installed)
    if expanded!=installed:raise ValueError('旧章节发生重排，不能只追加审计地图。')
    g=progress['game']
    if g.get('expedition_stages') or all(g.get('results',{}).get(sid,{}).get('cleared') for sid in base['levels']):
        g['expedition_unlocked']=True
    g['campaign']=expanded
    g.setdefault('audit_migration',{})['classic']='5.6.0'
    return True

def product(progress,questions):
    import desktop_product as p
    old=progress['game'].get('product_campaign')
    if not old or not any(q.get('book_id','').startswith('cpa_sj_') for q in questions):return
    installed=p.build_routes(questions)
    if old==installed:return
    bases=config()['trusted_550']['products']
    # The two variants are fresh 5.5.0 and its supported 5.4.1 upgrade chain.
    # An already expanded map must match the complete expected structure,
    # not merely a version or a bank fingerprint supplied in the save.
    for base in bases:
        expanded=extension(base,installed)
        if old==expanded:return
        if old==base:
            progress['game']['product_campaign']=expanded
            progress['game'].setdefault('audit_migration',{})['product']='5.6.0'
            return
    raise ValueError('保存的产品地图不属于受信升级链，原档保留，拒绝自动改写。')
