#!/usr/bin/env python3
"""文件整理助手：按类型归类文件夹中的散乱文件。"""

import argparse
import json
import shutil
import sys
from datetime import datetime
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

# 整理历史日志文件名（记录每次移动，用于 --undo）
HISTORY_NAME = ".organize_history.json"


def category_for(filename: str) -> str:
    """根据文件名返回类别文件夹名，未匹配则归入 Others。"""
    ext = Path(filename).suffix.lower()
    for category, exts in CATEGORY_MAP.items():
        if ext in exts:
            return category
    return "Others"


def plan_moves(target: Path) -> list[tuple[Path, Path]]:
    """
    扫描 target 目录，规划所有移动操作。

    规则：
    - 只处理直接子文件（不递归子文件夹、不移动文件夹）
    - 跳过隐藏文件（以 . 开头）
    - 跳过本脚本自身和整理历史日志
    - 目标重名时自动加序号（photo.png -> photo_1.png）

    返回 [(源路径, 目标路径), ...] 列表。
    """
    moves: list[tuple[Path, Path]] = []
    planned_destinations: set[Path] = set()  # 本次规划中已占用的目标名

    for item in sorted(target.iterdir()):
        if not item.is_file():
            continue  # 跳过子文件夹
        if item.name.startswith("."):
            continue  # 跳过隐藏文件
        if item.name in (SELF_NAME, HISTORY_NAME):
            continue  # 跳过脚本自身和历史日志

        category = category_for(item.name)
        dest = target / category / item.name

        # 重名处理：目标已存在（磁盘上或本次规划中）则加序号
        counter = 1
        while dest.exists() or dest in planned_destinations:
            dest = target / category / f"{item.stem}_{counter}{item.suffix}"
            counter += 1

        planned_destinations.add(dest)
        moves.append((item, dest))

    return moves


def print_plan(moves: list[tuple[Path, Path]]) -> None:
    """以清晰表格打印移动计划。"""
    if not moves:
        print("没有需要整理的文件，目录已经很整洁了。")
        return

    print(f"以下 {len(moves)} 个文件将被移动：")
    for src, dest in moves:
        print(f"  {src.name:<30} -> {dest.parent.name}/{dest.name}")

    # 按类别汇总
    from collections import Counter
    counts = Counter(dest.parent.name for _, dest in moves)
    summary = ", ".join(f"{name}({n})" for name, n in sorted(counts.items()))
    print(f"\n共 {len(moves)} 个文件：{summary}")


def load_history(target: Path) -> list[dict]:
    """读取目标目录的整理历史（不存在或损坏时返回空列表）。"""
    history_path = target / HISTORY_NAME
    if not history_path.exists():
        return []
    try:
        return json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_history(target: Path, history: list[dict]) -> None:
    """将整理历史写入目标目录。"""
    (target / HISTORY_NAME).write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def execute_moves(target: Path, moves: list[tuple[Path, Path]]) -> int:
    """
    执行移动并记录历史。每成功移动一个文件就落盘一次，崩溃也能恢复。
    返回成功移动的文件数。
    """
    history = load_history(target)
    operation = {
        "id": datetime.now().isoformat(timespec="seconds"),
        "target": str(target.resolve()),
        "moves": [],
    }
    history.append(operation)

    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dest))
        except OSError as e:
            print(f"  移动失败：{src.name} -> {dest.parent.name}/ ({e})", file=sys.stderr)
            continue
        operation["moves"].append({"src": str(src), "dest": str(dest)})
        save_history(target, history)  # 每移动一个就落盘，防止中途崩溃丢失记录

    return len(operation["moves"])


def undo_last(target: Path) -> bool:
    """
    撤销最近一次整理：把文件移回原位置。
    返回是否执行了撤销（没有历史时返回 False）。
    """
    history = load_history(target)
    if not history:
        print("没有可撤销的整理记录。")
        return False

    operation = history[-1]
    moves = operation["moves"]
    print(f"撤销 {operation['id']} 的整理（{len(moves)} 个文件）：")

    restored = 0
    # 逆序恢复，先处理后面的文件
    for record in reversed(moves):
        src = Path(record["src"])
        dest = Path(record["dest"])
        if not dest.exists():
            print(f"  跳过（目标已不存在）：{dest.name}", file=sys.stderr)
            continue
        try:
            shutil.move(str(dest), str(src))
        except OSError as e:
            print(f"  恢复失败：{dest.name} ({e})", file=sys.stderr)
            continue
        restored += 1
        # 类别文件夹空了就删除（只可能是本次整理创建的）
        if not any(dest.parent.iterdir()):
            dest.parent.rmdir()

    # 从历史中移除该操作（已完成的移动才移除）
    if restored == len(moves):
        history.pop()
        save_history(target, history)

    print(f"已恢复 {restored}/{len(moves)} 个文件。")
    return True


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
        if not args.directory:
            print("错误：--undo 需要指定目录参数：python organize.py <目录> --undo", file=sys.stderr)
            return 1
        target = Path(args.directory)
        if not target.is_dir():
            print(f"错误：目录不存在：{target}", file=sys.stderr)
            return 1
        undo_last(target)
        return 0

    target = Path(args.directory)
    if not target.is_dir():
        print(f"错误：目录不存在：{target}", file=sys.stderr)
        return 1

    print(f"目标目录：{target.resolve()}")
    print(f"模式：{'执行整理' if args.apply else '预览（不会移动任何文件）'}")
    print()

    moves = plan_moves(target)
    print_plan(moves)

    if not args.apply:
        if moves:
            print(f"\n确认无误后，运行：python organize.py {target} --apply")
        return 0

    if not moves:
        return 0

    moved = execute_moves(target, moves)
    print(f"\n已移动 {moved}/{len(moves)} 个文件。")
    print(f"历史记录：{target / HISTORY_NAME}（可用 --undo 撤销）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
