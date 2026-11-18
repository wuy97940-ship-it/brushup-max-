"""已安装地图的只读索引；磁盘以经过哈希校验的引用保存。"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache


class MapReferenceError(ValueError):
    """引用不是本包受信地图，必须显式恢复，不能静默重开。"""


def _immutable(*args, **kwargs):
    raise TypeError('安装地图是只读索引')


class ReadOnlyDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable

    def __deepcopy__(self, memo):
        return self


class ReadOnlyList(list):
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _immutable

    def __deepcopy__(self, memo):
        return self


def fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _freeze(value):
    if isinstance(value, dict):
        return ReadOnlyDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return ReadOnlyList(_freeze(item) for item in value)
    return value


@lru_cache(maxsize=1)
def indexes():
    import store
    path = store.resource_path('assets/static_campaigns570.json')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('schema') != 1 or not isinstance(raw.get('indexes'), dict):
        raise MapReferenceError('地图索引损坏，请恢复完整程序包。')
    result = {}
    for signature, value in raw['indexes'].items():
        if fingerprint(value) != signature:
            raise MapReferenceError('地图索引校验失败，请恢复完整程序包。')
        result[signature] = _freeze(value)
    return result


def hydrate(progress):
    g = progress.get('game')
    if not isinstance(g, dict):
        return progress
    refs = g.get('static_map_refs', {})
    if not isinstance(refs, dict) or any(key not in ('campaign', 'product_campaign') for key in refs):
        raise MapReferenceError('存档的地图引用无效，请保留存档并恢复原版本。')
    for key, signature in refs.items():
        index = indexes().get(signature)
        if index is None:
            raise MapReferenceError('此存档需要另一版本的题库地图，请保留存档并恢复对应完整程序包。')
        if key in g and g[key] != index:
            raise MapReferenceError('存档的地图与索引冲突，请恢复完整备份。')
        g[key] = index
    return progress


def seal(progress):
    """仅规范化阶段调用；不把未知旧地图伪装成受信索引。"""
    g = progress.get('game')
    if not isinstance(g, dict):
        return progress
    refs = {}
    for key in ('campaign', 'product_campaign'):
        value = g.get(key)
        if not isinstance(value, dict):
            continue
        if isinstance(value, ReadOnlyDict):
            signature = next((s for s, item in indexes().items() if item is value), None)
        else:
            signature = fingerprint(value)
        if signature in indexes():
            g[key] = indexes()[signature]
            refs[key] = signature
    if refs:
        g['static_map_refs'] = refs
    return progress


def compact(progress):
    g = progress.get('game')
    if not isinstance(g, dict):
        return progress
    refs = g.get('static_map_refs', {})
    if not refs:
        return progress
    result = dict(progress)
    result['game'] = dict(g)
    for key, signature in refs.items():
        if indexes().get(signature) is not g.get(key):
            raise MapReferenceError('地图引用未经加载校验，无法保存。')
        result['game'].pop(key, None)
    return result
