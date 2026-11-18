"""6.1主线展示和可跳过引导；不写入成绩、不发放奖励。"""
import json
import store
import desktop_product as product

CONFIG = json.loads(store.resource_path('assets/journey610.json').read_text(encoding='utf-8'))


def guide(g):
    return product.state(g).get('journey_guide', {'version': 1, 'dismissed': False, 'seen': []})


def set_guide(progress, context=None, *, dismissed=None, reset=False):
    state = product.state(progress['game'])
    value = {'version': 1, 'dismissed': False, 'seen': []} if reset else dict(guide(progress['game']))
    value['seen'] = list(value['seen'])
    if context in CONFIG['guide'] and context not in value['seen']:
        value['seen'].append(context)
    if dismissed is not None:
        value['dismissed'] = bool(dismissed)
    state['journey_guide'] = value
    return value


def chapter_view(g, world, chapter):
    config = CONFIG['worlds'][world['id']]
    ordinal = next(i for i, ch in enumerate(world['chapters']) if ch['id'] == chapter['id'])
    clears = sum(bool(g['results'].get(sid, {}).get('cleared')) for sid in chapter['stages'])
    completed = clears == len(chapter['stages'])
    available = product.can_play(g, chapter['stages'][0])
    return {'place': config['places'][ordinal % len(config['places'])],
            'mission': config['mission'].format(number=ordinal + 1),
            'clears': clears, 'total': len(chapter['stages']), 'completed': completed,
            'available': available,
            'status': '已点亮' if completed else '正在探索' if available else '待探索',
            'story': config['ending'] if completed else config['mission'].format(number=ordinal + 1)}


def next_main(g):
    active = g.get('active')
    if active and not active.get('settled'):
        return active['stage_id']
    world = g.get('world', 'accounting')
    known = {w['id'] for w in g['product_campaign']['worlds']}
    if world not in known:
        world = 'accounting'
    return product.next_stage(g, world_id=world)
