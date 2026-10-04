"""公开版真实题库加载、隔离存档、旧原创地图和公开导出边界。"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import game
import store
from check_public_release import scan
from sync_public_content import validate


class PublicContracts(unittest.TestCase):
    def test_desktop_map_has_required_world_display_fields(self):
        for world in [*game.WORLDS, *game.build_campaign(store.load_questions())["worlds"]]:
            for field in ("id", "prefix", "name", "subtitle"):
                self.assertTrue(world.get(field), (world["id"], field))

    def test_runtime_keeps_original_fields_and_map(self):
        bank = json.loads((ROOT / "content/original-bank.json").read_text("utf-8"))
        qs = store.load_questions()
        self.assertEqual({q["id"]: q for q in qs}, bank["questions"])
        self.assertEqual(len(qs), 704)
        self.assertEqual(len(game.build_campaign(qs)["levels"]), 128)

    def test_rejects_private_backup_without_mutating_it(self):
        progress = store.default_progress()
        progress["bank_family"] = "private-cpa"
        before = copy.deepcopy(progress)
        with self.assertRaises(ValueError):
            game.ensure_game(progress, store.load_questions())
        self.assertEqual(before, progress)

    def test_trusted_old_original_map_append_migration_preserves_records(self):
        qs = store.load_questions()
        progress = store.default_progress()
        game.ensure_game(progress, qs)
        original = json.loads((ROOT / "assets/finance_migration.json").read_text("utf-8"))["public_campaign"]
        progress["game"]["campaign"] = copy.deepcopy(original)
        progress["game"]["coins"] = 123
        game.ensure_game(progress, qs)
        self.assertEqual(progress["game"]["coins"], 123)
        self.assertEqual(progress["bank_family"], "original")
        self.assertEqual(len(progress["game"]["campaign"]["levels"]), 128)

    def test_tampered_original_map_is_not_trusted(self):
        qs = store.load_questions()
        progress = store.default_progress()
        game.ensure_game(progress, qs)
        progress["game"]["campaign"]["levels"]["accounting:01:normal:01"]["qids"] = [qs[0]["id"]]
        with self.assertRaises(ValueError):
            game.ensure_game(progress, qs)

    def test_scanner_fails_sensitive_file_without_echoing_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.private.config.json"
            path.write_text('user data', encoding="utf-8")
            self.assertIn("本机配置或用户存档", scan(path, Path(path.name)))

    def test_scanner_fails_embedded_credential_and_local_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            token = "ghp_" + "Z" * 36
            path.write_text(json.dumps({"value": token}), encoding="utf-8")
            errors = scan(path, Path(path.name), [token])
            self.assertIn("访问令牌", errors)
            self.assertIn("本地私密字段值", errors)
            self.assertNotIn(token, json.dumps(errors))

    def test_content_validator_rejects_non_original_question(self):
        bank = json.loads((ROOT / "content/original-bank.json").read_text("utf-8"))
        campaign = json.loads((ROOT / "content/campaign.json").read_text("utf-8"))
        bank["questions"][next(iter(bank["questions"]))]["book_id"] = "textbook_unapproved"
        with self.assertRaises(ValueError):
            validate(bank, campaign)


if __name__ == "__main__":
    unittest.main()
