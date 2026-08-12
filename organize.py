#!/usr/bin/env python3
"""文件整理助手：按类型归类文件夹中的散乱文件。"""

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 分类规则：扩展名 -> 类别文件夹名
# ---------------------------------------------------------------------------
CATEGORY_MAP = {
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico", ".heic", ".raw"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                  ".txt", ".md", ".csv", ".json", ".xml", ".epub"},
    "Videos":    {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"},
    "Audio":     {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Code":      {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".go",
                  ".rs", ".html", ".css", ".sh", ".sql"},
}

# 本脚本自身的文件名（整理时跳过自己）
SELF_NAME = Path(__file__).name


def category_for(filename: str) -> str:
    """根据文件名返回类别文件夹名，未匹配则归入 Others。"""
    ext = Path(filename).suffix.lower()
    for category, exts in CATEGORY_MAP.items():
        if ext in exts:
            return category
    return "Others"


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="按类型整理文件夹中的文件：先预览，确认后 --apply 执行，--undo 可撤销。"
    )
    parser.add_argument("directory", nargs="?", default=".",
                        help="要整理的文件夹路径（默认当前目录）")
    parser.add_argument("--apply", action="store_true",
                        help="真正执行整理（默认只预览）")
    parser.add_argument("--undo", action="store_true",
                        help="撤销最近一次整理")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.undo:
        print("撤销功能将在 4.4 步实现")
        return 0

    target = Path(args.directory)
    if not target.is_dir():
        print(f"错误：目录不存在：{target}", file=sys.stderr)
        return 1

    print(f"目标目录：{target.resolve()}")
    print(f"模式：{'执行整理' if args.apply else '预览（不会移动任何文件）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
