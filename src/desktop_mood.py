"""连续情绪与旧布尔存档兼容；只修改事务提供的角色副本。"""
from __future__ import annotations


def rules():
    from desktop_product import CONFIG
    return CONFIG['mood']


def value(hero):
    r = rules()
    legacy = r.get('legacy_initial', r['initial'])
    raw = hero.get('mood', r['low_threshold'] if hero.get('low_mood') else legacy)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raw = r['low_threshold'] if hero.get('low_mood') else legacy
    result = max(0, min(r['maximum'], int(raw)))
    # 旧控制器及已保存的旧操作仍写布尔；同步其含义，不覆盖数字进度。
    if hero.get('low_mood') and result > r['low_threshold']:
        return r['low_threshold']
    if hero.get('low_mood') is False and result <= r['low_threshold']:
        return legacy
    return result


def set_value(hero, number):
    r = rules()
    hero['mood'] = max(0, min(r['maximum'], int(number)))
    hero['low_mood'] = hero['mood'] <= r['low_threshold']
    hero['mood_version'] = 1
    return hero['mood']


def normalize(hero):
    return set_value(hero, value(hero))


def change(hero, delta):
    before = value(hero)
    after = set_value(hero, before + delta)
    return {'before': before, 'after': after, 'change': after - before}


def recover(hero, amount, *, floor=0):
    result = change(hero, max(0, amount))
    if result['after'] < floor:
        result['after'] = set_value(hero, floor)
        result['change'] = result['after'] - result['before']
    if not hero['low_mood']:
        hero.update(wrong_streak=[], correct_streak=0, rest_started=None)
    return result


def label(hero):
    number = value(hero)
    return '低落' if number <= rules()['low_threshold'] else '有点疲惫' if number < 50 else '平稳' if number < 80 else '开心'


def color(hero):
    return '#475569' if value(hero) <= rules()['low_threshold'] else '#EC6FA9'
