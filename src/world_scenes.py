"""场景选择独立于关卡、题目和解锁。"""
import json
import store

CONFIG = json.loads(store.resource_path('assets/world_scenes570.json').read_text(encoding='utf-8'))
SCENES = {s['id']: s for values in CONFIG['worlds'].values() for s in values}
BIOME_WORLDS = {'forest':'accounting','island':'law','stars':'finance','ruins':'audit'}

def chapter_scene(g, world_id, chapter_id=None):
    world = next(w for w in g['product_campaign']['worlds'] if w['id'] == world_id)
    ordinal = next((i for i,ch in enumerate(world['chapters']) if ch['id'] == chapter_id),0)
    values = CONFIG['worlds'][world_id]
    return values[ordinal % len(values)]['id']

def stage_scene(g, stage_id):
    item = g['product_campaign']['levels'].get(stage_id)
    return chapter_scene(g,item['world_id'],item['chapter_id']) if item else None

def question_scene(question):
    prefix = question.get('book_id','')
    world = 'audit' if prefix.startswith('cpa_sj_') else 'finance' if prefix.startswith('cpa_cg_') else 'law' if prefix.startswith('cpa_jjf_') else 'accounting'
    values = CONFIG['worlds'][world]
    return values[max(0,int(question.get('chapter_no') or 1)-1) % len(values)]['id']

def background(scene_id, biome, dark=False):
    scene = SCENES.get(scene_id)
    if scene is None and biome in BIOME_WORLDS:
        scene = CONFIG['worlds'][BIOME_WORLDS[biome]][0]
    if scene:
        return store.resource_path('assets/backgrounds/'+scene.get('night' if dark else 'day',scene['day']))
    return store.resource_path(f"assets/backgrounds/{biome}_{'night' if dark else 'day'}_v520.png")
