#!/usr/bin/env python3
"""organize.py 的自动化测试：覆盖 requirements.md 中的全部测试场景。

运行方式：python3 test_organize.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ORGANIZE = Path(__file__).parent / "organize.py"
HISTORY = ".organize_history.json"


def run(*args: str) -> subprocess.CompletedProcess:
    """运行 organize.py，返回结果。"""
    return subprocess.run(
        [sys.executable, str(ORGANIZE), *args],
        capture_output=True,
        text=True,
    )


def make_messy_dir(base: Path, name: str = "messy") -> Path:
    """创建一个装满散文件的测试目录。"""
    d = base / name
    d.mkdir()
    files = [
        "photo.jpg", "wallpaper.png", "photo.PNG",      # 图片（含大小写扩展名）
        "report.pdf", "notes.txt", "data.csv",           # 文档
        "movie.mp4", "clip.mkv",                         # 视频
        "song.mp3", "voice.wav",                         # 音频
        "backup.zip", "source.tar.gz",                   # 压缩包
        "script.py", "style.css",                        # 代码
        "mystery.bin", "noext",                          # 其他
    ]
    for name_ in files:
        (d / name_).touch()
    # 隐藏文件、子文件夹、空子文件夹
    (d / ".hidden.png").touch()
    (d / "keep_me").mkdir()
    (d / "keep_me" / "important.txt").touch()
    (d / "empty_dir").mkdir()
    return d


class TestOrganize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="organize_test_")
        self.messy = make_messy_dir(Path(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def top_files(self) -> set[str]:
        """顶层可见文件（隐藏文件不计入，它们本就不该被整理）。"""
        return {p.name for p in self.messy.iterdir()
                if p.is_file() and not p.name.startswith(".")}

    # ---- 场景 a: 预览模式不产生任何移动 ----
    def test_preview_moves_nothing(self):
        result = run(str(self.messy))
        self.assertEqual(result.returncode, 0)
        self.assertIn("预览", result.stdout)
        # 预览后，顶层文件一个都没少，也没有新增任何类别文件夹
        self.assertEqual(len(self.top_files()), 16)
        self.assertEqual([p for p in self.messy.iterdir() if p.is_dir()],
                         [self.messy / "keep_me", self.messy / "empty_dir"])

    # ---- 场景 b: apply 后文件归类正确 ----
    def test_apply_organizes_correctly(self):
        result = run(str(self.messy), "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertIn("已移动 16/16", result.stdout)
        # 各类别文件都在正确位置
        expected = {
            "Images": {"photo.jpg", "wallpaper.png", "photo.PNG"},
            "Documents": {"report.pdf", "notes.txt", "data.csv"},
            "Videos": {"movie.mp4", "clip.mkv"},
            "Audio": {"song.mp3", "voice.wav"},
            "Archives": {"backup.zip", "source.tar.gz"},
            "Code": {"script.py", "style.css"},
            "Others": {"mystery.bin", "noext"},
        }
        for category, names in expected.items():
            cat_dir = self.messy / category
            self.assertTrue(cat_dir.is_dir(), f"缺少类别目录 {category}")
            self.assertEqual({p.name for p in cat_dir.iterdir()}, names,
                             f"{category} 内容不符")
        # 隐藏文件留在原地（不参与整理），子文件夹未被移动
        self.assertTrue((self.messy / ".hidden.png").exists())
        self.assertTrue((self.messy / "keep_me" / "important.txt").exists())

    # ---- 场景 c: 重名文件加序号 ----
    def test_duplicate_names_get_suffix(self):
        (self.messy / "Images").mkdir()
        (self.messy / "Images" / "photo.jpg").touch()  # 已存在的同名文件
        result = run(str(self.messy), "--apply")
        self.assertEqual(result.returncode, 0)
        images = {p.name for p in (self.messy / "Images").iterdir()}
        self.assertIn("photo.jpg", images)      # 原有文件未被覆盖
        self.assertIn("photo_1.jpg", images)    # 新文件加了序号

    # ---- 场景 d: undo 完整还原 ----
    def test_undo_restores_everything(self):
        run(str(self.messy), "--apply")
        result = run(str(self.messy), "--undo")
        self.assertEqual(result.returncode, 0)
        self.assertIn("已恢复 16/16", result.stdout)
        # 所有文件回到顶层，文件名原样
        self.assertEqual(len(self.top_files()), 16)
        for name in ["photo.jpg", "wallpaper.png", "photo.PNG", "report.pdf",
                     "notes.txt", "data.csv", "movie.mp4", "clip.mkv",
                     "song.mp3", "voice.wav", "backup.zip", "source.tar.gz",
                     "script.py", "style.css", "mystery.bin", "noext"]:
            self.assertIn(name, self.top_files())
        # 类别文件夹全部被清理
        self.assertEqual([p for p in self.messy.iterdir() if p.is_dir()],
                         [self.messy / "keep_me", self.messy / "empty_dir"])

    def test_undo_without_history_is_friendly(self):
        result = run(str(self.messy), "--undo")
        self.assertEqual(result.returncode, 0)
        self.assertIn("没有可撤销", result.stdout)

    # ---- 场景 e: 重复运行幂等 ----
    def test_idempotent(self):
        run(str(self.messy), "--apply")
        result = run(str(self.messy), "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertIn("没有需要整理", result.stdout)

    # ---- 场景 f: 不存在的目录友好报错 ----
    def test_nonexistent_dir_errors(self):
        result = run(str(Path(self.tmp) / "nope"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("错误：目录不存在", result.stderr)

    # ---- 额外: 空目录 ----
    def test_empty_dir(self):
        empty = Path(self.tmp) / "empty"
        empty.mkdir()
        result = run(str(empty), "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertIn("没有需要整理", result.stdout)

    # ================= v2 功能 =================

    # ---- v2: 自定义分类规则（与默认合并） ----
    def test_custom_rules(self):
        config = Path(self.tmp) / "rules.json"
        config.write_text(json.dumps({
            "Design": [".sketch", ".fig"],       # 新类别
            "Images": [".webp", ".tiff"],        # 扩展已有类别
        }), encoding="utf-8")
        (self.messy / "logo.sketch").touch()
        (self.messy / "photo.tiff").touch()

        result = run(str(self.messy), "--config", str(config), "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertIn("已移动 18/18", result.stdout)
        self.assertTrue((self.messy / "Design" / "logo.sketch").exists())
        self.assertTrue((self.messy / "Images" / "photo.tiff").exists())

    def test_custom_rules_without_config_uses_defaults(self):
        """不传 --config 时，新扩展名应落入 Others。"""
        (self.messy / "logo.sketch").touch()
        result = run(str(self.messy), "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.messy / "Others" / "logo.sketch").exists())

    def test_invalid_config_errors(self):
        bad = Path(self.tmp) / "bad.json"
        bad.write_text("not json{", encoding="utf-8")
        result = run(str(self.messy), "--config", str(bad))
        self.assertEqual(result.returncode, 1)
        self.assertIn("不是合法 JSON", result.stderr)

        missing = Path(self.tmp) / "nope.json"
        result = run(str(self.messy), "--config", str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertIn("配置文件不存在", result.stderr)

    # ---- v2: 按日期归档 ----
    def test_by_date(self):
        (self.messy / "photo.jpg").touch()
        os.utime(self.messy / "photo.jpg", (1715759400, 1715759400))  # 2024-05-15
        result = run(str(self.messy), "--by-date", "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.messy / "2024" / "05" / "photo.jpg").exists())

    def test_by_date_undo_cleans_nested_folders(self):
        """按日期归档后 undo，应清理 2024/05 和空的 2024 两层。"""
        (self.messy / "photo.jpg").touch()
        os.utime(self.messy / "photo.jpg", (1715759400, 1715759400))
        run(str(self.messy), "--by-date", "--apply")
        result = run(str(self.messy), "--undo")
        self.assertEqual(result.returncode, 0)
        self.assertIn("已恢复 16/16", result.stdout)
        self.assertFalse((self.messy / "2024").exists(), "2024 文件夹应被清理")

    # ---- v2: 清理空文件夹 ----
    def test_clean_empty_preview_does_nothing(self):
        result = run(str(self.messy), "--clean-empty")
        self.assertEqual(result.returncode, 0)
        self.assertIn("将清理 1 个空文件夹", result.stdout)
        self.assertTrue((self.messy / "empty_dir").exists(), "预览不应删除")

    def test_clean_empty_apply_removes_with_cascade(self):
        (self.messy / "junk_dir").mkdir()
        (self.messy / "nested" / "deep").mkdir(parents=True)
        result = run(str(self.messy), "--clean-empty", "--apply")
        self.assertEqual(result.returncode, 0)
        self.assertIn("已清理", result.stdout)
        self.assertFalse((self.messy / "empty_dir").exists())
        self.assertFalse((self.messy / "junk_dir").exists())
        self.assertFalse((self.messy / "nested").exists(), "级联清理应移除空父目录")
        # 非空文件夹不受影响
        self.assertTrue((self.messy / "keep_me").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
