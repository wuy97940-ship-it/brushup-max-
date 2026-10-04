"""核对公开来源、完整题库导出、共享代码和常见凭据；错误只报告位置与类型。"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sync_public_content import validate

SKIP = {".git", "node_modules", ".expo", ".venv", "venv", "__pycache__", ".qa", "dist", "dist-ios"}
FORBIDDEN_PARTS = {"private", "原始pdf", "资料", "storage", "network", "webstorage", "alternativeservices", "browser-profile"}
FORBIDDEN_EXT = {".pdf", ".sqlite", ".sqlite3", ".db", ".wal", ".exe", ".p8", ".p12", ".pem", ".mobileprovision", ".pyc"}
PATTERNS = {
    "微信真实AppID": re.compile(r"wx[0-9a-f]{16}\b", re.I),
    "私钥": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "访问令牌": re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{25,}|gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9_-]{25,})\b"),
    "凭据赋值": re.compile(r"(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[\"'][A-Za-z0-9_./+-]{24,}[\"']", re.I),
    "本机绝对路径": re.compile(r"[CD]:[/\\](?:Codex|Claude|Users)[/\\]", re.I),
}


def files():
    for parent, directories, names in os.walk(ROOT):
        directories[:] = sorted(d for d in directories if d not in SKIP)
        for name in directories:
            item = Path(parent) / name
            if item.is_symlink():
                raise ValueError(f"公开仓库不携带本机链接：{item.relative_to(ROOT).as_posix()}")
        for name in sorted(names):
            item = Path(parent) / name
            rel = item.relative_to(ROOT)
            if item.is_symlink():
                raise ValueError(f"公开仓库不携带本机链接：{rel.as_posix()}")
            if item.is_file():
                yield item, rel


def scan(path, relative, denied=()):
    errors = []
    if any(part.lower() in FORBIDDEN_PARTS for part in relative.parts) or path.suffix.lower() in FORBIDDEN_EXT:
        errors.append("禁止公开的文件类型或目录")
    if path.name.startswith(".env") or path.name.lower() in {"cookies", "login data", "progress.json", "project.private.config.json"}:
        errors.append("本机配置或用户存档")
    if path.stat().st_size > 50 * 1024 * 1024:
        errors.append("文件超过本仓库50MiB审查阈值")
    if path.suffix.lower() not in {".png", ".ico", ".ttf", ".woff", ".woff2"}:
        text = path.read_text("utf-8", errors="replace")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                errors.append(label)
        if any(value and len(value) >= 6 and value in text for value in denied):
            errors.append("本地私密字段值")
    return errors


def check(denied=()):
    bank = json.loads((ROOT / "content/original-bank.json").read_text("utf-8"))
    campaign = json.loads((ROOT / "content/campaign.json").read_text("utf-8"))
    questions = validate(bank, campaign)
    errors = []
    included = list(files())
    for path, rel in included:
        errors.extend({"file": rel.as_posix(), "rule": error} for error in scan(path, rel, denied))
    desktop = json.loads((ROOT / "data/questions.json").read_text("utf-8"))
    if {q["id"]: q for q in desktop["questions"]} != questions:
        errors.append({"file": "data/questions.json", "rule": "桌面题目字段与主库不同"})
    if (ROOT / "content/original-bank.json").read_bytes() != (ROOT / "ios-app/src/content/original-bank.json").read_bytes():
        errors.append({"file": "ios-app/src/content/original-bank.json", "rule": "Expo题库字节不同"})
    recovered = {}
    for path in (ROOT / "miniprogram/packages").glob("*/bank.js"):
        match = re.search(r"decodeBank\('([A-Za-z0-9+/=]+)'\)", path.read_text("utf-8"))
        if not match:
            continue
        chunk = json.loads(gzip.decompress(base64.b64decode(match[1])))
        if set(recovered) & set(chunk):
            errors.append({"file": path.relative_to(ROOT).as_posix(), "rule": "微信题目重复"})
        recovered.update(chunk)
    if recovered != questions:
        errors.append({"file": "miniprogram/packages", "rule": "微信完整字段与主库不同"})
    baseline = json.loads((ROOT / "miniprogram/data/migration_baseline.json").read_text("utf-8"))
    if baseline["family"] != "original":
        errors.append({"file": "miniprogram/data/migration_baseline.json", "rule": "存档家族未隔离"})
    provenance = json.loads((ROOT / "ios-app/shared-provenance.json").read_text("utf-8"))
    for pair in provenance["shared_pairs"]:
        source, target = ROOT / pair["source"], ROOT / pair["target"]
        if source.read_bytes() != target.read_bytes() or hashlib.sha256(target.read_bytes()).hexdigest() != pair["sha256"]:
            errors.append({"file": pair["target"], "rule": "共享来源或摘要改变"})
    config = json.loads((ROOT / "ios-app/app.json").read_text("utf-8"))["expo"]
    if config.get("owner") or config.get("extra", {}).get("eas", {}).get("projectId"):
        errors.append({"file": "ios-app/app.json", "rule": "仍绑定原部署账号"})
    mini_config = json.loads((ROOT / "miniprogram/project.config.json").read_text("utf-8"))
    if mini_config["appid"] != "touristappid":
        errors.append({"file": "miniprogram/project.config.json", "rule": "未使用独立体验配置"})
    return {"passed": not errors, "question_count": len(questions), "stages": len(campaign["levels"]),
            "files_checked": len(included), "bytes_checked": sum(f.stat().st_size for f, _ in included),
            "all_question_fields_equal": recovered == questions,
            "shared_pairs_checked": len(provenance["shared_pairs"]), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deny-file", help="可选的本机私密字段JSON；不复制文件、不输出字段值")
    parser.add_argument("--output", default=".qa/public-release-check.json")
    args = parser.parse_args()
    denied = []
    if args.deny_file:
        values = json.loads(Path(args.deny_file).read_text("utf-8"))
        denied = [str(v) for v in values.values() if isinstance(v, (str, int))]
    try:
        report = check(denied)
    except (ValueError, OSError, KeyError) as exc:
        report = {"passed": False, "errors": [{"rule": type(exc).__name__}]}
    target = ROOT / args.output
    if not target.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("检查输出必须在当前公开仓库内")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
