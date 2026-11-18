"""最多两局的完整存档；当前局引用原子进度文件，切局才保存另一局。"""
from __future__ import annotations
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

BEIJING=timezone(timedelta(hours=8))
LIMIT=2

def _files(directory):
    directory=Path(directory).resolve()
    home=directory/'game-saves'
    home.mkdir(parents=True,exist_ok=True)
    return home,home/'index.json',directory/'progress.json'

def _epoch(progress):return progress.get('reset_epoch') or 'legacy'

def _validate(meta):
    records=meta.get('slots',[])
    ids=[item.get('id','') for item in records]
    if meta.get('schema')!=1 or not 1<=len(ids)<=LIMIT or len(set(ids))!=len(ids) or any(not re.fullmatch(r'[0-9a-f]{32}',key) for key in ids) or meta.get('active') not in ids:
        raise ValueError('存档记录格式无效，请保留目录和备份。')
    return meta

def _read(index):
    if not index.exists():return None
    for path in (index,index.with_name(index.name+'.last-good')):
        try:return _validate(json.loads(path.read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError,AttributeError):pass
    raise ValueError('两局存档记录损坏，请保留存档目录和备份。')

def _write(index,meta):
    import store
    _validate(meta)
    if index.exists():
        old=index.read_bytes()
        try:_validate(json.loads(old))
        except (ValueError,TypeError,AttributeError):pass
        else:store._atomic_bytes(index.with_name(index.name+'.last-good'),old)
    store._atomic_bytes(index,json.dumps(meta,ensure_ascii=False,separators=(',',':')).encode('utf-8'))

def _slot_file(home,key):
    if not re.fullmatch(r'[0-9a-f]{32}',key):raise ValueError('存档编号不正确')
    return home/(key+'.json')

RETIRED_KEEP=5

def _retire_slot(home,slot_id):
    """逐出的旧局槽文件先原子归档再移除；自动恢复路径（如双档损坏回退空档）不得直接删档。"""
    import store
    source=_slot_file(home,slot_id)
    if not source.is_file():return
    try:
        retired=home/'retired';retired.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(BEIJING).strftime('%Y%m%d-%H%M%S')
        target=retired/f'{slot_id}-{stamp}.json'
        store._atomic_bytes(target,source.read_bytes())
        source.unlink(missing_ok=True)
        stale=sorted(retired.glob('*.json'))
        for old in stale[:-RETIRED_KEEP]:
            try:old.unlink()
            except OSError:pass
    except OSError:
        pass  # 归档失败保留原文件（成为index外游离文件，records 不列出，不影响换局）

def ensure_current(directory,progress=None):
    import store
    home,index,current=_files(directory)
    p=progress if progress is not None else store._valid_progress(current)
    epoch=_epoch(p);meta=_read(index)
    if meta is not None:
        active=next(item for item in meta['slots'] if item['id']==meta['active'])
        if active['epoch']==epoch:return meta
        known=next((item for item in meta['slots'] if item['epoch']==epoch),None)
        if known:
            meta['active']=known['id'];_write(index,meta);return meta
    else:meta={'schema':1,'active':None,'next_sequence':1,'slots':[]}
    number=meta['next_sequence'];meta['next_sequence']=number+1
    record={'id':uuid.uuid4().hex,'epoch':epoch,'sequence':number,
            'created_at':datetime.now(BEIJING).isoformat()}
    previous_active=meta['active']
    removed=[item for item in meta['slots'] if item['id']!=previous_active]
    meta['slots']=[item for item in meta['slots'] if item['id']==previous_active]+[record]
    meta['active']=record['id']
    _write(index,meta)
    for item in removed:_retire_slot(home,item['id'])
    return meta

def archive_current(directory):
    import store
    home,index,current=_files(directory)
    if not current.exists():return None
    content=current.read_bytes()
    p=json.loads(content)
    if not isinstance(p,dict):raise ValueError('当前存档格式无效')
    meta=ensure_current(directory,p)
    target=_slot_file(home,meta['active'])
    store._atomic_bytes(target,content)
    if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(content).digest():
        raise OSError('当前局存档复制核验失败')
    return meta

def reset_completed(directory,progress):
    return ensure_current(directory,progress)

def pending_switch(directory):
    return (_files(directory)[0]/'switch-commit.json').is_file()

def recover_switch(directory):
    import store
    home,index,current=_files(directory);journal=home/'switch-commit.json'
    if not journal.exists():return
    transaction=json.loads(journal.read_text(encoding='utf-8'))
    if not isinstance(transaction, dict):
        raise ValueError('待恢复的存档切换记录无效')
    meta=_read(index);key=transaction.get('target');p=transaction.get('progress')
    if meta is None or key not in [item.get('id') for item in meta.get('slots', []) if isinstance(item, dict)] or not isinstance(p,dict):
        raise ValueError('待恢复的存档切换记录无效')
    from static_campaigns import hydrate
    hydrate(p)
    record=next(item for item in meta['slots'] if item['id']==key)
    if record['epoch']!=_epoch(p):raise ValueError('存档切换身份不符')
    content=store.encode_progress(p)
    store._atomic_bytes(current.with_name(current.name+'.last-good'),content)
    store._atomic_bytes(current,content)
    meta['active']=key;_write(index,meta)
    journal.unlink()

def restore(directory,identifier):
    import store
    home,index,current=_files(directory)
    journal=home/'switch-commit.json'
    if journal.exists():
        transaction=json.loads(journal.read_text(encoding='utf-8'))
        if not isinstance(transaction, dict) or transaction.get('target')!=identifier:raise ValueError('请先完成上次存档切换')
        recover_switch(directory)
        return store._valid_progress(current)
    meta=ensure_current(directory)
    if identifier==meta['active']:return store._valid_progress(current)
    record=next((item for item in meta['slots'] if item['id']==identifier),None)
    if record is None:raise ValueError('这个存档点已被更新替换')
    candidate=store._valid_progress(_slot_file(home,identifier))
    if _epoch(candidate)!=record['epoch'] or not isinstance(candidate.get('game'),dict):
        raise ValueError('存档身份或内容不正确')
    archive_current(directory)
    from static_campaigns import compact
    store._atomic_bytes(journal,json.dumps({'target':identifier,'progress':compact(candidate)},ensure_ascii=False,separators=(',',':')).encode('utf-8'))
    recover_switch(directory)
    return copy.deepcopy(candidate)

def records(directory):
    import store
    home,index,current=_files(directory);meta=ensure_current(directory)
    rows=[]
    for item in reversed(meta['slots']):
        active=item['id']==meta['active'];path=current if active else _slot_file(home,item['id'])
        row={**item,'active':active,'available':False}
        try:
            p=store._valid_progress(path);g=p.get('game',{});s=g.get('product',{})
            if _epoch(p)!=item['epoch']:raise ValueError('存档身份不符')
            heroes=s.get('heroes',{})
            row.update(available=True,saved_at=datetime.fromtimestamp(path.stat().st_mtime,BEIJING).strftime('%Y-%m-%d %H:%M:%S'),
                       answered=len(p.get('answered',{})),wrong=len(p.get('wrong_book',[])),
                       favorites=len(p.get('favorites',[])),coins=g.get('coins',0),
                       hero=g.get('skin','xiaoyuan'),heroes=len(heroes),
                       inventory=len(g.get('inventory',[])),has_active=bool(g.get('active') or p.get('practice') or g.get('hunting',{}).get('active')))
        except (OSError,ValueError,TypeError):pass
        rows.append(row)
    return rows
