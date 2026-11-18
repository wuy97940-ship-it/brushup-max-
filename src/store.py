"""题库加载与进度持久化。

修复要点：
- 加载题库时合并 questions + extras，过滤掉无效客观题（缺 options 或 ABCD 不全）。
- 主观题（计算分析题 / 综合题 / 简答题 / 论述题）做运行时清洗：从 stem 拆出参考答案。
- 进度读写做容错，损坏时自动回退默认值并备份原文件。
- 章节 / 题型枚举集中在 questions_meta()，避免 GUI 多次重算。
- v2.0 新增 book 维度（书本/题库子集）：所有筛选、统计、错题、收藏、进度按 book_id 隔离。
"""
from __future__ import annotations

import json
import os
import copy
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from collections import OrderedDict
import threading

_progress_bytes_cache = OrderedDict()
_progress_bytes_lock = threading.RLock()
_PROGRESS_CACHE_LIMIT = 8 * 1024 * 1024


def _file_stamp(path):
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _remember_bytes(path, content, stamp=None):
    if len(content) > _PROGRESS_CACHE_LIMIT:
        return
    key = str(path.absolute())
    try:
        current = _file_stamp(path)
    except OSError:
        return
    if stamp is not None and stamp != current:
        return
    stamp = current
    with _progress_bytes_lock:
        _progress_bytes_cache[key] = (stamp, content)
        _progress_bytes_cache.move_to_end(key)
        while (len(_progress_bytes_cache) > 64 or
               sum(len(row[1]) for row in _progress_bytes_cache.values()) > _PROGRESS_CACHE_LIMIT):
            _progress_bytes_cache.popitem(last=False)


def _trusted_bytes(path):
    """只复用已读/已刷盘且文件身份、长度、修改时间均未变的字节。"""
    stamp = _file_stamp(path)
    key = str(path.absolute())
    with _progress_bytes_lock:
        cached = _progress_bytes_cache.get(key)
        if cached is not None and cached[0] == stamp:
            _progress_bytes_cache.move_to_end(key)
            return cached[1]
    content = path.read_bytes()
    if _file_stamp(path) == stamp:
        _remember_bytes(path, content, stamp)
    return content

from books import (
    BOOKS,
    ALL_BOOKS_VALUE,
    book_by_id,
    book_id_from_legacy,
    book_name_to_id,
)


def app_data_dir() -> Path:
    """用户级数据目录：~/.xy_shuati/"""
    # 隔离测试与便携预览使用独立目录；正常运行仍保留原用户级存档。
    override = os.environ.get("XY_SHUATI_DATA_DIR")
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    d = Path(override) if override else home / ".xy_shuati_public"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resource_path(rel: str) -> Path:
    """支持 PyInstaller 打包后从 _MEIPASS 读 data 文件。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / rel


# 题型分类
CHOICE_TYPES = {"单选题", "多选题", "不定项题", "单远题"}
OBJECTIVE_TYPES = {"单选题", "多选题", "判断题", "不定项题", "单远题"}
SUBJECTIVE_TYPES = {"计算分析题", "综合题", "简答题", "论述题", "案例分析题"}  # v3修复：案例分析题此前被静默过滤

# 主观题清洗用：题干 / 答案分隔，及答案后噪声截断
_RE_ANS_SPLIT = re.compile(r"\n\s*答\s*案\s*\n")
_RE_REQ_LINE = re.compile(r"\n\s*要\s*求\s*[:：]")
_RE_TAIL_STOP = re.compile(
    r"(?:进\s*涨\s*分\s*技巧|进\s*应试|进\s*常见|进\s*解题|进\s*应用|"
    r"#\s*速懂案例|◇\s*原理|应试摘要|"
    r"【\s*提示\s*】|【\s*归纳\s*】|"
    r"\n\s*例\s*题\s*[-—－]\s*答\s*案|"
    r"\n\s*第\s*[一二三四五六七八九十]+\s*章\s)"
)


def _split_subjective(stem: str) -> tuple[str, str]:
    """从主观题 stem 拆出 (题干, 参考答案)。

    优先按 "答案" 行分隔；退化为找 "要求：" 行后第一段作为答案。
    最后用 _RE_TAIL_STOP 截掉答案末尾的章末附加内容。
    """
    text = (stem or "").replace("\r", "").strip()
    if not text:
        return "", ""
    body, answer = text, ""

    m = _RE_ANS_SPLIT.search(text)
    if m:
        body = text[:m.start()].rstrip()
        answer = text[m.end():].strip()
    else:
        req = _RE_REQ_LINE.search(text)
        if req:
            after = text[req.end():]
            # "要求：" 这一行末（其实是从此处往后第一行的末尾）作为题干尾
            line_end_idx = after.find("\n")
            if line_end_idx >= 0:
                body = text[:req.end() + line_end_idx].rstrip()
                answer = after[line_end_idx:].strip()

    if answer:
        cut = _RE_TAIL_STOP.search(answer)
        if cut:
            answer = answer[:cut.start()].rstrip()
    return body, answer


def is_subjective(q: dict) -> bool:
    return (q.get("type") or "") in SUBJECTIVE_TYPES


def _question_valid(q: dict) -> bool:
    qtype = q.get("type") or ""
    stem_ok = bool((q.get("stem") or "").strip())
    if not stem_ok:
        return False
    if qtype in SUBJECTIVE_TYPES:
        # 主观题：有题干即可（答案/解析可能缺）
        return True
    if qtype not in OBJECTIVE_TYPES:
        return False
    if not q.get("answer"):
        return False
    # 修正OCR错误类型
    if qtype == "单远题":
        q["type"] = "单选题"
        qtype = "单选题"
    if qtype in CHOICE_TYPES:
        opts = q.get("options") or {}
        if not isinstance(opts, dict):
            return False
        if not all(opts.get(L) for L in "ABCD"):
            return False
    return True


def load_questions() -> list[dict]:
    """加载并合并 questions + extras；主观题二次清洗。"""
    path = resource_path("data/questions.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return prepare_questions(raw)


def prepare_questions(raw: dict) -> list[dict]:
    """离线候选和正式加载使用相同验证、清洗及排序，保持旧地图编排。"""
    primary = list(raw.get("questions") or [])
    extras = list(raw.get("extras") or [])

    valid: list[dict] = []
    seen_ids: set[str] = set()

    for src in (primary, extras):
        for q in src:
            if not _question_valid(q):
                continue
            qid = q.get("id")
            if not qid or qid in seen_ids:
                continue
            # v3题库重塑：带_status标记且非published的题不进刷题池（D级/隔离题）
            if q.get("_status") and q.get("_status") != "published":
                continue
            seen_ids.add(qid)
            qq = dict(q)
            # 兜底补 book_id（从旧 book 字段映射）
            if not qq.get("book_id"):
                bid = book_id_from_legacy(qq.get("book") or "")
                if bid:
                    qq["book_id"] = bid
            if is_subjective(qq) and not qq.get("subquestions"):
                body, ans = _split_subjective(qq.get("stem") or "")
                qq["stem"] = body or qq.get("stem") or ""
                if not (qq.get("explanation") or "").strip():
                    qq["explanation"] = ans
                if not (qq.get("answer") or "").strip():
                    qq["answer"] = "（参见参考答案）" if ans else ""
            valid.append(qq)

    # 按 BOOKS 顺序排序
    book_order = {b["id"]: i for i, b in enumerate(BOOKS)}
    valid.sort(key=lambda q: (
        book_order.get(q.get("book_id") or "", 999),
        q.get("chapter_no", 0),
        0 if q.get("type") in OBJECTIVE_TYPES else 1,
        q.get("num", 0),
        q.get("type", ""),
    ))
    return valid


def questions_meta(qs: list[dict]) -> dict[str, Any]:
    """返回章节列表 / 题型分布等元信息（全局，不区分 book）。"""
    chapters: list[str] = []
    type_counter: dict[str, int] = {}
    chapter_stats: dict[str, dict[str, int]] = {}
    for q in qs:
        ch = f"{q.get('book') or ''} {q.get('chapter') or ''}".strip()
        if ch not in chapters:
            chapters.append(ch)
            chapter_stats[ch] = {"total": 0}
        chapter_stats[ch]["total"] += 1
        type_counter[q["type"]] = type_counter.get(q["type"], 0) + 1
    return {
        "chapters": chapters,
        "type_counter": type_counter,
        "chapter_stats": chapter_stats,
    }


def book_meta(qs: list[dict]) -> dict[str, dict[str, Any]]:
    """按 book_id 聚合：chapters / type_counter / total。
    返回 {book_id: {chapters: [...], type_counter: {...}, total: int, name: str}}
    """
    book_order = {b["id"]: i for i, b in enumerate(BOOKS)}
    out: dict[str, dict[str, Any]] = {}
    for q in qs:
        for bid in q.get('book_ids',[q.get('book_id')]):
            if not bid:continue
            b = out.setdefault(bid, {
                "chapters": [], "_chset": set(), "type_counter": {}, "total": 0,
                "name": (book_by_id(bid) or {}).get("name", bid),
                "category": (book_by_id(bid) or {}).get("category", ""),
                "order": book_order.get(bid, 999),
            })
            ch = q.get("chapter") or ""
            if ch and ch not in b["_chset"]:
                b["_chset"].add(ch);b["chapters"].append(ch)
            b["type_counter"][q["type"]] = b["type_counter"].get(q["type"], 0) + 1
            b["total"] += 1
    for b in out.values():
        b.pop("_chset", None)
    return out


def available_books(qs: list[dict]) -> list[dict]:
    """返回有题的书本元数据，按 BOOKS 中的顺序。"""
    have = {bid for q in qs for bid in q.get('book_ids',[q.get('book_id')]) if bid}
    return [b for b in BOOKS if b["id"] in have]


def filter_by_book(qs: list[dict], book_id: str | None) -> list[dict]:
    if not book_id or book_id == ALL_BOOKS_VALUE:
        return qs
    return [q for q in qs if book_id in q.get('book_ids',[q.get('book_id')])]


PROGRESS_FILE = "progress.json"


def default_progress() -> dict:
    return {
        "answered": {},      # qid -> {"correct": bool, "user_answer": str, "ts": float}
        "wrong_book": [],    # 错题 qid 列表（去重，保持顺序）
        "favorites": [],     # 收藏 qid
        "last": {            # 上次刷题位置
            "mode": "顺序刷题",
            "filter_book": ALL_BOOKS_VALUE,
            "filter_chapter": "全部章节",
            "filter_type": "全部题型",
            "index": 0,
            "qids": [],
        },
        "theme": "system",
        "scaling": 1.0,
    }


def _valid_progress(path):
    data = json.loads(_trusted_bytes(path).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("存档格式不正确")
    from static_campaigns import hydrate
    return hydrate(data)


def load_progress() -> dict:
    f = app_data_dir() / PROGRESS_FILE
    if (f.parent / "game-saves/switch-commit.json").exists():
        import desktop_save_slots as slots
        slots.recover_switch(f.parent)
    # 重开以单个持久化提交日志为恢复界限，防止旧last-good复活旧学习记录。
    reset_commit = f.with_name(f.name + '.reset-commit')
    if reset_commit.exists():
        try:
            fresh = _valid_progress(reset_commit)
            if not fresh.get('reset_epoch'):
                raise ValueError('重开提交标记无效')
            content = reset_commit.read_bytes()
            _atomic_bytes(f.with_name(f.name + '.last-good'), content)
            _atomic_bytes(f, content)
            import desktop_save_slots as slots
            slots.reset_completed(f.parent, fresh)
            reset_commit.unlink()
        except (OSError, ValueError, UnicodeError):
            # 已确认的重开候选优先，磁盘仍失败时保持候选；不能回读旧恢复副本。
            if 'fresh' in locals() and fresh.get('reset_epoch'):
                return _normalize_progress(fresh)
            raise ValueError('重开恢复标记无法读取，请保留目录并恢复完整备份。')
    if not f.exists():
        recovery = f.with_name(f.name + '.last-good')
        if recovery.exists():
            # Windows替换中断可能已把上一主档移至备份，不能当作空的新局。
            return _normalize_progress(_valid_progress(recovery))
        return default_progress()
    try:
        data = _valid_progress(f)
    except (OSError, ValueError, UnicodeError) as error:
        from static_campaigns import MapReferenceError
        if isinstance(error, MapReferenceError):
            raise
        try:
            import uuid
            historical = sorted(f.parent.glob(f.name + ".broken-*"))
            prefix = f.name + ".broken-"
            stamps = [p.name[len(prefix):].split("-", 1)[0] for p in historical]
            # 两种时钟均可同值；递增前缀保证轮换按留存顺序，UUID仅防重名。
            latest = max((int(s) for s in stamps if s.isdecimal()), default=0)
            sequence = max(time.time_ns(), latest + 1)
            stamp = f"{sequence:020d}-{time.monotonic_ns():020d}-{uuid.uuid4().hex}"
            bak = f.with_name(f.name + ".broken-" + stamp)
            shutil.copy2(f, bak)
            for old in historical[:-2]:
                old.unlink()
        except OSError:
            pass
        try:
            data = _valid_progress(f.with_name(f.name + ".last-good"))
        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError('当前存档和恢复副本均无法读取。原文件已保留，请恢复完整备份或明确选择重新开始。') from error
    return _normalize_progress(data)


def _normalize_progress(data):
    base = default_progress()
    if isinstance(data, dict):
        base.update(data)
    for k, v in default_progress().items():
        base.setdefault(k, v)
    if not isinstance(base.get("last"), dict):
        base["last"] = default_progress()["last"]
    else:
        for k, v in default_progress()["last"].items():
            base["last"].setdefault(k, v)
    if not isinstance(base.get("answered"), dict):
        base["answered"] = {}
    if not isinstance(base.get("wrong_book"), list):
        base["wrong_book"] = []
    if not isinstance(base.get("favorites"), list):
        base["favorites"] = []
    return base


def _open_atomic_temp(path):
    """独占新临时文件；由调用者flush、fsync后原子替换主档。"""
    return path.open('xb')


def _atomic_bytes(path, content):
    import uuid
    tmp = path.with_name(path.name + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with _open_atomic_temp(tmp) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # 外部进程（杀软扫描/索引服务）的瞬时读句柄会让 replace 抛 PermissionError，
        # 同一已刷盘候选文件短退避重试；不重算事务，耗尽后finally清理tmp。
        last_error = None
        written_stamp = _file_stamp(tmp)
        for delay in (0.0, 0.05, 0.15, 0.45):
            if delay:
                time.sleep(delay)
            try:
                tmp.replace(path)
                _remember_bytes(path, content, written_stamp)
                last_error = None
                break
            except PermissionError as error:
                last_error = error
        if last_error is not None:
            raise last_error
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def clone_progress(p: dict) -> dict:
    """可变进度深隔离；已校验的安装地图只读共享，避免每题复制近一兆地图。"""
    return copy.deepcopy(p)


def encode_progress(p: dict) -> bytes:
    from static_campaigns import compact
    return json.dumps(compact(p), ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _retain_previous_file(main, recovery, previous):
    """上一完整档独立刷盘；旧恢复副本改名留作失败回退，不创建硬链接。"""
    import uuid
    tag=f'.{os.getpid()}.{uuid.uuid4().hex}.tmp'
    rollback=recovery.with_name(recovery.name+'.rollback'+tag)
    main_stamp = _file_stamp(main)
    if _trusted_bytes(main) != previous:
        raise OSError('保存前主档已变化')
    try:
        if recovery.exists():
            recovery.replace(rollback)
        _atomic_bytes(recovery,previous)
        if _file_stamp(main) != main_stamp:
            raise OSError('保存恢复副本期间主档已变化')
        return rollback if rollback.exists() else None
    except OSError:
        if rollback.exists():
            rollback.replace(recovery)
        raise


def _native_backup_enabled():
    return os.name == 'nt'


def _native_replace_file(main, candidate, recovery):
    import ctypes
    from ctypes import wintypes
    function = ctypes.WinDLL('kernel32', use_last_error=True).ReplaceFileW
    function.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                         wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
    function.restype = wintypes.BOOL
    if not function(str(main), str(candidate), str(recovery), 0, None, None):
        raise ctypes.WinError(ctypes.get_last_error())


def _replace_with_previous(main, recovery, content, previous):
    """新候选刷盘一次；系统替换同时保留已经刷盘的上一主档，备份不共享文件对象。"""
    import uuid
    tag = f'.{os.getpid()}.{uuid.uuid4().hex}.tmp'
    candidate = main.with_name(main.name + tag)
    rollback = recovery.with_name(recovery.name + '.rollback' + tag)
    before = _file_stamp(main)
    if _trusted_bytes(main) != previous:
        raise OSError('保存前主档已变化')
    moved = False
    try:
        with _open_atomic_temp(candidate) as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        written = _file_stamp(candidate)
        if _file_stamp(main) != before:
            raise OSError('候选刷盘期间主档已变化')
        if recovery.exists():
            recovery.replace(rollback);moved = True
        try:
            for delay in (0.0, 0.05, 0.15, 0.45):
                if delay:time.sleep(delay)
                if _file_stamp(main) != before:
                    raise OSError('替换前主档已变化')
                try:
                    _native_replace_file(main, candidate, recovery)
                    break
                except OSError as error:
                    if getattr(error, 'winerror', None) not in (5, 32, 33) or delay == 0.45:
                        raise
        except OSError:
            # ERROR_UNABLE_TO_MOVE_REPLACEMENT_2可能已将上一主档移至备份。
            # 先恢复主档；仍失败则保留该备份和旧rollback，重开优先读取备份。
            if not main.exists() and recovery.exists():
                recovery.replace(main)
            if moved and rollback.exists() and main.exists():
                rollback.replace(recovery)
            raise
        _remember_bytes(main, content, written)
        _remember_bytes(recovery, previous, before)
        if moved:
            try:rollback.unlink(missing_ok=True)
            except OSError:pass
    finally:
        # 主档仍缺失时保留全部可恢复文件，不能以清理覆盖异常结果。
        if main.exists():
            try:candidate.unlink(missing_ok=True)
            except OSError:pass


def save_progress(p: dict) -> bool:
    try:
        f = app_data_dir() / PROGRESS_FILE
        if (f.parent / "game-saves/switch-commit.json").exists():
            return False
        # 部分重开已写主档但元数据尚未提交时，必须续完同一事务；否则下次读取会覆盖重试之后的新进度。
        if f.with_name(f.name + '.reset-commit').exists():
            return save_new_progress(p)
        content = encode_progress(p)
        recovery = f.with_name(f.name + ".last-good")
        # 保留上一份已验证正常的完整档，再持久化并原子替换本次档。
        rollback=None
        if f.exists():
            previous = _trusted_bytes(f)
            if previous == content:
                # 相同候选不重复写主档，但初次保存或恢复副本损坏时仍须补齐备份。
                try:
                    _valid_progress(recovery)
                except (OSError, ValueError, UnicodeError):
                    _atomic_bytes(recovery, content)
                return True
            try:
                prior = json.loads(previous.decode("utf-8"))
                valid = isinstance(prior, dict)
            except (ValueError, UnicodeError):
                valid = False
                prior = {}
            if p.get('reset_epoch') and p['reset_epoch'] != prior.get('reset_epoch'):
                return save_new_progress(p)
            if valid:
                if _native_backup_enabled():
                    _replace_with_previous(f,recovery,content,previous)
                    return True
                rollback=_retain_previous_file(f,recovery,previous)
        else:
            # 第一份成功保存即应能恢复，不依赖用户随后修改进度。
            _atomic_bytes(recovery, content)
        try:
            _atomic_bytes(f, content)
        except (OSError, ValueError, TypeError):
            # 回退也可能被外部读句柄阻止；失败时保留原恢复副本供重试/人工恢复。
            # 不能在finally中删掉尚未恢复的唯一原副本。
            if rollback is not None and rollback.exists():rollback.replace(recovery)
            raise
        if rollback is not None:
            try:rollback.unlink(missing_ok=True)
            except OSError:pass  # 主档已持久化，清理旧副本失败不撤销已提交的事务。
        return True
    except (OSError, ValueError, TypeError):
        return False


def save_new_progress(p: dict) -> bool:
    """完整归档存档及恢复副本，再提交同代新档；仅用于已确认的重新开始。"""
    import hashlib
    try:
        if not p.get('reset_epoch'):
            raise ValueError('缺少重开事务编号')
        directory = app_data_dir()
        f = directory / PROGRESS_FILE
        commit = f.with_name(f.name + '.reset-commit')
        if not commit.exists():
            import desktop_save_slots as slots
            slots.archive_current(directory)
            archive = directory / 'reset-archives' / p['reset_epoch']
            if not archive.resolve().is_relative_to((directory / 'reset-archives').resolve()):
                raise ValueError('重开归档目录越界')
            archive.mkdir(parents=True, exist_ok=True)
            records = []
            for source in sorted(directory.glob('progress*')):
                if not source.is_file() or source.suffix == '.tmp':
                    continue
                target = archive / source.name
                shutil.copy2(source, target)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if digest != hashlib.sha256(target.read_bytes()).hexdigest():
                    raise OSError('重开前存档归档核验失败')
                records.append({'file': source.name, 'sha256': digest, 'bytes': source.stat().st_size})
            _atomic_bytes(archive / 'manifest.json', json.dumps(records, ensure_ascii=False).encode('utf-8'))
            content = encode_progress(p)
            _atomic_bytes(commit, content)
        else:
            fresh = _valid_progress(commit)
            if fresh.get('reset_epoch') != p['reset_epoch']:
                raise ValueError('已有不同的待重开事务，请先恢复')
            content = commit.read_bytes()
        _atomic_bytes(f.with_name(f.name + '.last-good'), content)
        _atomic_bytes(f, content)
        import desktop_save_slots as slots
        slots.reset_completed(directory, json.loads(content))
        commit.unlink()
        return True
    except (OSError, ValueError, TypeError):
        return False


def record_answer(p: dict, qid: str, correct: bool, user_answer: str) -> None:
    p["answered"][qid] = {
        "correct": bool(correct),
        "user_answer": user_answer,
        "ts": time.time(),
    }
    if not correct:
        if qid not in p["wrong_book"]:
            p["wrong_book"].append(qid)
    else:
        if qid in p["wrong_book"]:
            p["wrong_book"].remove(qid)


def clear_answer(p: dict, qid: str) -> None:
    p["answered"].pop(qid, None)
    if qid in p["wrong_book"]:
        p["wrong_book"].remove(qid)


def toggle_favorite(p: dict, qid: str) -> bool:
    fav = p["favorites"]
    if qid in fav:
        fav.remove(qid)
        return False
    fav.append(qid)
    return True


def overall_stats(p: dict, qs: list[dict], book_id: str | None = None) -> dict[str, Any]:
    """统计：可按 book_id 限定范围。
    answered/wrong/fav 计数会与传入的题目集合 qs 相交以保证维度一致。
    """
    qs_scope = filter_by_book(qs, book_id) if book_id else qs
    qid_set = {q["id"] for q in qs_scope}
    ans = p.get("answered", {})
    answered_in_scope = {qid: v for qid, v in ans.items() if qid in qid_set}
    n_ans = len(answered_in_scope)
    n_right = sum(1 for v in answered_in_scope.values() if v.get("correct"))
    rate = (n_right / n_ans * 100) if n_ans else 0.0
    wrong = [q for q in p.get("wrong_book", []) if q in qid_set]
    fav = [q for q in p.get("favorites", []) if q in qid_set]
    return {
        "total": len(qs_scope),
        "answered": n_ans,
        "right": n_right,
        "wrong_count": len(wrong),
        "fav_count": len(fav),
        "rate": rate,
    }


def chapter_progress(p: dict, qs: list[dict], book_id: str | None = None) -> list[dict[str, Any]]:
    qs_scope = filter_by_book(qs, book_id) if book_id else qs
    ans = p.get("answered", {})
    bucket: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for q in qs_scope:
        # v3.2: 章节名统一显示中文书名（原先直接拼 book_id）
        bn = (book_by_id(q.get("book_id") or "") or {}).get("name") or q.get("book") or ""
        key = f"{bn} · {q.get('chapter') or ''}".strip(" ·")
        if key not in bucket:
            bucket[key] = {"name": key, "total": 0, "answered": 0, "right": 0, "book_id": q.get("book_id")}
            order.append(key)
        bucket[key]["total"] += 1
        rec = ans.get(q["id"])
        if rec:
            bucket[key]["answered"] += 1
            if rec.get("correct"):
                bucket[key]["right"] += 1
    out = []
    for k in order:
        item = bucket[k]
        item["rate"] = (item["right"] / item["answered"] * 100) if item["answered"] else 0.0
        out.append(item)
    return out


def book_progress(p: dict, qs: list[dict]) -> list[dict[str, Any]]:
    """按书本聚合：返回 [{book_id, name, category, total, answered, right, rate, wrong, fav}]"""
    ans = p.get("answered", {})
    wrong_set = set(p.get("wrong_book", []))
    fav_set = set(p.get("favorites", []))
    bm = book_meta(qs)
    out = []
    for bid, meta in sorted(bm.items(), key=lambda kv: kv[1]["order"]):
        scope = filter_by_book(qs,bid)
        qid_set = {q["id"] for q in scope}
        ans_in = {qid: v for qid, v in ans.items() if qid in qid_set}
        n_ans = len(ans_in)
        n_right = sum(1 for v in ans_in.values() if v.get("correct"))
        out.append({
            "book_id": bid,
            "name": meta["name"],
            "category": meta["category"],
            "total": meta["total"],
            "answered": n_ans,
            "right": n_right,
            "rate": (n_right / n_ans * 100) if n_ans else 0.0,
            "wrong": sum(1 for qid in scope if qid["id"] in wrong_set),
            "fav": sum(1 for qid in scope if qid["id"] in fav_set),
        })
    return out


def question_number(question: dict) -> str:
    """保留原题号；旧整数序号从零转为显示序号，缺号题使用稳定ID尾号。"""
    number = question.get("num")
    if isinstance(number, int):
        return str(number + 1)
    if number is not None and str(number).strip():
        return str(number)
    tail = str(question["id"]).rsplit("-", 1)[-1]
    return str(int(tail)) if tail.isdigit() else str(question["id"])
