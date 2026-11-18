"""同一道题在答题、错题和收藏页使用同一份文字讲解。"""
from __future__ import annotations


def explanation_text(question: dict) -> str:
    return str(question.get('detailed_explanation') or question.get('explanation') or '').strip()


def display_options(question: dict) -> dict:
    return question.get('display_options') or question.get('options') or {}


def is_audit(question: dict) -> bool:
    return question.get('subject') == 'CPA审计' or str(question.get('book_id', '')).startswith('cpa_sj_')
