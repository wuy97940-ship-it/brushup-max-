"""题库加载与进度持久化。

修复要点：
- 加载题库时合并 questions + extras，过滤掉无效客观题（缺 options 或 ABCD 不全）。
- 主观题（计算分析题 / 综合题 / 简答题 / 论述题）做运行时清洗：从 stem 拆出参考答案。
- 进度读写做容错，损坏时自动回退默认值并备份原文件。
- 章节 / 题型枚举集中在 questions_meta()，避免 GUI 多次重算。
- v2.0 新增 book 维度（书本/题库子集）：所有筛选、统计、错题、收藏、进度按 book_id 隔离。
"""
from __future__ import annotations


def question_number(question: dict) -> str:
    """保留原题号；旧整数序号从零转为显示序号，缺号题使用稳定ID尾号。"""
    number = question.get("num")
    if isinstance(number, int):
        return str(number + 1)
    if number is not None and str(number).strip():
        return str(number)
    tail = str(question["id"]).rsplit("-", 1)[-1]
    return str(int(tail)) if tail.isdigit() else str(question["id"])

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

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
        bid = q.get("book_id") or ""
        if not bid:
            continue
        b = out.setdefault(bid, {
            "chapters": [],
            "_chset": set(),
            "type_counter": {},
            "total": 0,
            "name": (book_by_id(bid) or {}).get("name", bid),
            "category": (book_by_id(bid) or {}).get("category", ""),
            "order": book_order.get(bid, 999),
        })
        ch = q.get("chapter") or ""
        if ch and ch not in b["_chset"]:
            b["_chset"].add(ch)
            b["chapters"].append(ch)
        b["type_counter"][q["type"]] = b["type_counter"].get(q["type"], 0) + 1
        b["total"] += 1
    for b in out.values():
        b.pop("_chset", None)
    return out


def available_books(qs: list[dict]) -> list[dict]:
    """返回有题的书本元数据，按 BOOKS 中的顺序。"""
    have = {q.get("book_id") for q in qs if q.get("book_id")}
    return [b for b in BOOKS if b["id"] in have]


def filter_by_book(qs: list[dict], book_id: str | None) -> list[dict]:
    if not book_id or book_id == ALL_BOOKS_VALUE:
        return qs
    return [q for q in qs if q.get("book_id") == book_id]


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


def load_progress() -> dict:
    f = app_data_dir() / PROGRESS_FILE
    if not f.exists():
        return default_progress()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        try:
            bak = f.with_suffix(".json.broken")
            shutil.copy2(f, bak)
        except Exception:
            pass
        return default_progress()
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


def save_progress(p: dict) -> bool:
    f = app_data_dir() / PROGRESS_FILE
    tmp = f.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)
        return True
    except Exception:
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
        scope = [q for q in qs if q.get("book_id") == bid]
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
