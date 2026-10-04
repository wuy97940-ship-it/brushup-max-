"""书本（Book）元数据与映射。

定义所有题库的 book_id / 分类 / 显示名 / 旧 book 字段兼容映射。
v3.5: AI训练师题库已随考试结束下线，5本AI书从书目中移除（历史数据见 git 与 backup\）。
"""
from __future__ import annotations

# 分类
CAT_MID = "中级"
CAT_CPA = "注会"
CAT_AI = "AI训练师"  # 已随AI题库下线停用，保留常量避免历史引用报错

# (book_id, category, display_name, legacy_books_set)
# legacy_books_set 是旧 questions.json 中 book 字段的可能取值；用于迁移
BOOKS: list[dict] = [{'id': 'acc_original_v01', 'category': '原创', 'name': '原创会计基础', 'full_name': '原创会计基础', 'legacy': set()}, {'id': 'law_original_v01', 'category': '原创', 'name': '原创经济法基础', 'full_name': '原创经济法基础', 'legacy': set()}, {'id': 'cg_original_v02', 'category': '原创', 'name': '原创财务成本管理', 'full_name': '原创财务成本管理', 'legacy': set()}]

ALL_BOOKS_VALUE = "全部书本"


def book_by_id(book_id: str) -> dict | None:
    for b in BOOKS:
        if b["id"] == book_id:
            return b
    return None


def book_id_from_legacy(legacy_book: str) -> str | None:
    for b in BOOKS:
        if legacy_book in b["legacy"]:
            return b["id"]
    return None


def book_filter_values() -> list[str]:
    """返回 UI 下拉框的可选值（含"全部书本"）。"""
    return [ALL_BOOKS_VALUE] + [b["name"] for b in BOOKS]


def book_name_to_id(name: str) -> str | None:
    for b in BOOKS:
        if b["name"] == name:
            return b["id"]
    return None


def book_id_to_name(bid: str) -> str:
    b = book_by_id(bid)
    return b["name"] if b else bid
