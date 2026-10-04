"""从公开内容主库无损生成桌面、微信和Expo数据，不读取教材或用户存档。"""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS = {"acc_original_v01": {"name": "原创会计基础", "world": "accounting"},
         "law_original_v01": {"name": "原创经济法基础", "world": "law"},
         "cg_original_v02": {"name": "原创财务成本管理", "world": "finance"}}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_js(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// 由 scripts/sync_public_content.py 生成，保留所有题目字段。\nmodule.exports="
                    + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def validate(bank, campaign):
    questions = bank["questions"]
    if not questions or any(not qid.startswith("orig-") or q["id"] != qid
                            or q.get("book_id") not in BOOKS for qid, q in questions.items()):
        raise ValueError("公开主库只接受已登记的原创题号与书目")
    for q in questions.values():
        if q.get("stem_images") or q.get("reference_images"):
            raise ValueError("公开主库不能带入扫描题图")
        origin = q.get("authorship", q.get("source_ref", {}))
        if origin.get("kind") != "project_original":
            raise ValueError("题目缺少项目原创来源声明")
        if not all(q.get(k) for k in ("stem", "answer", "explanation")):
            raise ValueError("题干、答案或解析缺失")
    # 公开版沿用已发布的身份指纹；它不是私人地图的题号集合哈希。
    # 内容保真另以原文件SHA及各端完整字段比较核对，不能擅自换指纹协议。
    if not re.fullmatch(r"[a-f0-9]{64}", bank["fingerprint"]) or campaign["bank_fingerprint"] != bank["fingerprint"]:
        raise ValueError("题库与地图指纹不一致")
    arranged = [qid for level in campaign["levels"].values() for qid in level["qids"]]
    if len(arranged) != len(questions) or set(arranged) != set(questions):
        raise ValueError("主线必须全量且唯一覆盖题目")
    for level in campaign["levels"].values():
        if level["world_id"] == "finance" and len(level["qids"]) > (1 if level["kind"] == "boss" else 10):
            raise ValueError("财管关卡题量超出规则")
    return questions


def main():
    bank = json.loads((ROOT / "content/original-bank.json").read_text("utf-8"))
    campaign = json.loads((ROOT / "content/campaign.json").read_text("utf-8"))
    questions = validate(bank, campaign)
    # 主库原字节进入Expo；桌面与微信仅改变容器格式，不删减讲解字段。
    (ROOT / "ios-app/src/content/original-bank.json").write_bytes((ROOT / "content/original-bank.json").read_bytes())
    (ROOT / "ios-app/src/content/campaign.json").write_bytes((ROOT / "content/campaign.json").read_bytes())
    write_json(ROOT / "data/questions.json", {"schema_version": 1, "bank_family": "original",
               "bank_id": bank["id"], "bank_fingerprint": bank["fingerprint"], "questions": list(questions.values()), "extras": []})
    write_json(ROOT / "data/campaign.json", campaign)
    mini = ROOT / "miniprogram"
    base = json.loads((ROOT / "ios-app/src/shared/data/base.json").read_text("utf-8"))
    write_js(mini / "data/rules.js", {**base, "campaign": campaign})
    routes, packages = {}, []
    for world in campaign["worlds"]:
        name = world["id"] + "1"
        ids = [qid for chapter in world["chapters"] for sid in chapter["stages"]
               for qid in campaign["levels"][sid]["qids"]]
        chunk = {qid: questions[qid] for qid in ids}
        raw = json.dumps(chunk, ensure_ascii=False, separators=(",", ":")).encode()
        encoded = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode()
        folder = mini / "packages" / name
        folder.mkdir(parents=True, exist_ok=True)
        script = "// 完整原创题目，无损离线编码。\nmodule.exports=require('../../utils/bank_codec').decodeBank('" + encoded + "');\n"
        if len(script.encode()) >= 1500 * 1024:
            raise ValueError("原创科目分包已超出安全阈值，请按完整关卡进一步分包")
        (folder / "bank.js").write_text(script, encoding="utf-8")
        page = folder / "pages/quiz"
        page.mkdir(parents=True, exist_ok=True)
        (page / "index.js").write_text("const createQuiz=require('../../../../utils/quiz');\nPage(createQuiz(require('../../bank')));\n", encoding="utf-8")
        (page / "index.wxml").write_text('<include src="../../../../templates/quiz.wxml"/>\n', encoding="utf-8")
        (page / "index.wxss").write_text('@import "../../../../templates/quiz.wxss";\n', encoding="utf-8")
        write_json(page / "index.json", {"navigationBarTitleText": "小圆的原创挑战", "usingComponents": {
                   "cat-actor": "/components/actor/index", "study-text": "/components/study-text/index"}})
        packages.append({"root": "packages/" + name, "name": name, "pages": ["pages/quiz/index"]})
        routes.update({qid: "/packages/" + name + "/pages/quiz/index" for qid in chunk})
    if (mini / "packages/financeArt/bank.js").is_file():
        packages.append({"root": "packages/financeArt", "name": "financeArt", "pages": ["pages/ready/index"]})
    meta = [{k: q[k] for k in ("id", "book_id", "chapter", "chapter_no", "type", "difficulty") if k in q}
            | {"world_id": BOOKS[q["book_id"]]["world"]} for q in questions.values()]
    write_js(mini / "data/questions.js", {"meta": meta, "routes": routes, "books": {k: v["name"] for k, v in BOOKS.items()}})
    app = json.loads((mini / "app.json").read_text("utf-8"))
    app["subpackages"] = packages
    write_json(mini / "app.json", app)
    print(json.dumps({"question_count": len(questions), "stages": len(campaign["levels"]),
                      "bank_id": bank["id"], "bank_fingerprint": bank["fingerprint"],
                      "wechat_subpackages": len(packages), "all_fields_retained": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
