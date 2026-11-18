"""Only migrate explicitly trusted shipped maps; never attach old awards to new groups."""
import copy,json
from collections import defaultdict
import store

def config():return json.loads(store.resource_path('assets/challenge_migration.json').read_text('utf-8'))
def aliases():return json.loads(store.resource_path('data/question_aliases.json').read_text('utf-8'))
def mapped(key,table):return table.get(key,{}).get('canonical',key)

def references(progress):
    table=aliases()
    if progress.get('qid_alias_migration')=='5.5.0':return
    # Preserve an exact private in-save history before converting option letters.
    for field in ('answered','wrong_book','favorites','last'):
        progress.setdefault('pre550_alias_history',{})[field]=copy.deepcopy(progress.get(field))
    def visit(value,key=''):
        if isinstance(value,dict):
            out={}
            for k,v in value.items():
                if k=='pre550_alias_history':
                    out[k]=copy.deepcopy(v);continue
                newkey=mapped(k,table);item=visit(v,k)
                if k in table and isinstance(item,dict) and isinstance(item.get('user_answer'),str):
                    mapping=table[k]['option_map'];answer=item['user_answer']
                    if answer and all(c in mapping for c in answer):item['user_answer']=''.join(sorted(mapping[c] for c in answer))
                # If two historical ids merge, keep the latest answer, archive remains exact.
                if newkey in out and isinstance(item,dict) and isinstance(out[newkey],dict):
                    if item.get('ts',0)<out[newkey].get('ts',0):continue
                out[newkey]=item
            return out
        if isinstance(value,list):
            items=[visit(v,key) for v in value]
            return list(dict.fromkeys(items)) if all(isinstance(v,str) for v in items) else items
        return mapped(value,table) if isinstance(value,str) else value
    transformed=visit(progress)
    progress.clear();progress.update(transformed);progress['qid_alias_migration']='5.5.0'

def classic(progress,installed):
    g=progress['game'];old=g['campaign'];c=config()['trusted_541']['classic']
    legacy=json.loads(store.resource_path('assets/finance_migration.json').read_text('utf-8')).get('private_campaign')
    if old not in (c,legacy):raise ValueError('保存的地图不属于已核验的1026或5.4.1题库，原档保留。')
    references(progress);g=progress['game']
    old=g['campaign']
    g.setdefault('legacy_campaign_levels',{}).update(copy.deepcopy(old['levels']))
    if all(g.get('results',{}).get(sid,{}).get('cleared') for sid in old['levels']) or g.get('expedition_stages'):g['expedition_unlocked']=True
    g['campaign']=copy.deepcopy(installed)
    g['bank_migration_version']='5.5.0'

def product(progress,questions):
    import desktop_product as p
    g=progress['game'];old=g.get('product_campaign')
    if not old or old.get('version')==3:return
    trusted=config()['trusted_541']['product']
    # references() may have already converted the single historical duplicate.
    table=aliases();trusted=copy.deepcopy(trusted)
    for level in trusted['levels'].values():level['qids']=list(dict.fromkeys(mapped(qid,table) for qid in level['qids']))
    if old!=trusted:raise ValueError('产品地图不属于受信5.4.1基线，不能自动改组旧成绩。')
    seen={qid for level in old['levels'].values() for qid in level['qids']}
    grouped=defaultdict(list)
    for q in questions:
        if q['id'] not in seen:
            world='finance' if q['book_id'].startswith('cpa_cg_') else 'law' if q['book_id'].startswith('cpa_jjf_') else 'accounting'
            grouped[world,int(q.get('chapter_no') or 0)].append(q)
    from desktop_challenge import rank
    for (world_id,number),pool in sorted(grouped.items()):
        world=next(w for w in old['worlds'] if w['id']==world_id)
        chapter=next((ch for ch in world['chapters'] if ch['number']==number),None)
        if chapter is None:
            chapter={'id':f'v5:{world_id}:{number:02d}','number':number,'title':pool[0]['chapter'],'stages':[],'biome':world['biome']};world['chapters'].append(chapter);world['chapters'].sort(key=lambda c:c['number'])
        objective=[q for q in pool if not store.is_subjective(q)];elite=sorted(objective,key=lambda q:(-rank(q),q['id']))[:10]
        reserved={q['id'] for q in elite};normal=[q for q in objective if q['id'] not in reserved]
        groups=[('normal',normal[i:i+10],f'补充探索关 {i//10+1}') for i in range(0,len(normal),10)]
        groups += [('case',[q],'补充案例挑战') for q in pool if store.is_subjective(q)]
        if elite:groups.append(('boss',elite,'补充章节 Boss'))
        for i,(kind,qs,name) in enumerate(groups):
            sid=f'{chapter["id"]}:new550:{kind}:{i:03d}';chapter['stages'].append(sid)
            old['levels'][sid]={'id':sid,'world_id':world_id,'chapter_id':chapter['id'],'chapter_no':number,'chapter_title':chapter['title'],'kind':kind,'name':name,'biome':world['biome'],'qids':[q['id'] for q in qs],'subjective':store.is_subjective(qs[0]),'product_route':True}
    old.update(version=3,bank_fingerprint=p.build_routes(questions)['bank_fingerprint'],migration_origin='trusted-5.4.1-preserved-stage-ids')
