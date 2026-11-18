"""四件成套匹配与原子穿戴，不增加属性或第二份装备权益。"""
from __future__ import annotations
import copy
import json
import store

CONFIG=json.loads(store.resource_path('assets/suit_config.json').read_text(encoding='utf-8'))
SUITS={item['id']:item for item in CONFIG['suits']}

def pose_key(item,pose):
    # 新套装有独立行走/出招帧；优先使用其原动作，旧小团继续按旧姿态别名。
    if pose in item['poses']:return pose
    import desktop_wardrobe as wardrobe
    canonical=wardrobe.canonical_pose(item['hero'],pose)
    if canonical in item['poses']:return canonical
    generic={'smile':'happy','wave':'walk','proud':'chest','sad':'hurt','cry':'hurt','sit':'think'}.get(canonical,canonical)
    return generic if generic in item['poses'] else 'idle'

def shop_entries():
    """商店中的整套展示；购买权益仍来自原四件商品。"""
    import desktop_product as p
    return [{**item, 'name':p.HEROES[item['hero']]['name']+' · '+item['name'],
             'category':'装备', 'subcategory':'套装', 'kind':'suit',
             'display_rarity':p.CONFIG['equipment_tiers'][item['rarity']]['name'],
             'description':'服装、头饰、鞋子、爪套四件成套；配齐显示完整造型，含12个动作。',
             'image':'assets/market/items/'+item['id']+'.png',
             'thumbnail':'assets/market/thumbs/'+item['id']+'.png'}
            for item in SUITS.values()]

def shop_status(g,identifier):
    import desktop_product as p
    absent=missing(g,identifier)
    return {'owned_parts':4-len(absent), 'missing_items':absent,
            'missing_coins':sum(p.SHOP_CATALOG[key]['price'] for key in absent),
            'equipped':matched(g)==SUITS[identifier]}

def matched(g):
    return next((item for item in SUITS.values() if item['hero']==g['skin'] and
                 all(g.get(slot)==identifier for slot,identifier in item['required_items'].items())),None)

def preview(g,identifier):
    import desktop_product as p
    item=SUITS[identifier];result=p.hero_preview(g,item['hero'])
    result.update(item['required_items'])
    return result

def missing(g,identifier):
    import desktop_product as p
    return [key for key in SUITS[identifier]['required_items'].values() if not p.owned_count(g,key)]

def equip(progress,identifier,token):
    import desktop_product as p
    g=progress['game'];s=p.state(g);item=SUITS[identifier]
    prior=s['transactions'].get(token)
    if prior:
        if prior['operation']!='suit_equip' or prior['item']!=identifier:raise ValueError('操作编号与套装不一致。')
        return copy.deepcopy(prior['result'])
    p.require_action(g);p._target_hero(g,item['hero'])
    absent=missing(g,identifier)
    if absent:raise ValueError('请先拥有全部四件商品，再一键穿戴整套。')
    s['appearances'][item['hero']].update(item['required_items'])
    if p.hero_id(g)==item['hero']:p._sync_appearance(g,item['hero'])
    p.refresh_capacity(g)
    result={'flow':'suits','operation':'suit_equip','target':identifier,'hero':item['hero']}
    s['transactions'][token]={'operation':'suit_equip','item':identifier,'result':copy.deepcopy(result)}
    return result
