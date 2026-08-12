#!/usr/bin/env python3
"""文件整理助手：按类型/日期归类文件夹中的散乱文件。"""

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 默认分类规则：扩展名 -> 类别文件夹名
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


def load_rules(config_path: str | None) -> dict[str, set[str]] | None:
    """加载分类规则：默认规则 + 自定义规则合并（自定义可扩展/覆盖同名类别）。

    配置文件格式：{"类别名": [".ext1", ".ext2", ...], ...}
    返回 None 表示配置有误（已打印错误信息）。
    """
    rules = {cat: set(exts) for cat, exts in CATEGORY_MAP.items()}
    if not config_path:
        return rules
    path = Path(config_path)
    if not path.is_file():
        print(f"错误：配置文件不存在：{path}", file=sys.stderr)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"错误：配置文件不是合法 JSON：{e}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print("错误：配置文件应为 JSON 对象（类别名 -> 扩展名数组）", file=sys.stderr)
        return None
    for category, exts in data.items():
        if not isinstance(exts, list) or not all(isinstance(e, str) for e in exts):
            print(f"错误：类别 {category!r} 的值应为扩展名数组", file=sys.stderr)
            return None
        rules.setdefault(category, set()).update(
            f".{ext.lstrip('.').lower()}" for ext in exts
        )
    return rules


def category_for(filename: str, rules: dict[str, set[str]]) -> str:
    """根据文件名返回类别文件夹名，未匹配则归入 Others。"""
    ext = Path(filename).suffix.lower()
    for category, exts in rules.items():
        if ext in exts:
            return category
    return "Others"


def date_folder_for(item: Path) -> str:
    """按文件的修改时间返回归档文件夹 YYYY/MM。"""
    mtime = datetime.fromtimestamp(item.stat().st_mtime)
    return f"{mtime.year:04d}/{mtime.month:02d}"


def plan_moves(target: Path, rules: dict[str, set[str]],
               by_date: bool = False) -> list[tuple[Path, Path]]:
    """
    扫描 target 目录，规划所有移动操作。

    规则：
    - 只处理直接子文件（不递归子文件夹、不移动文件夹）
    - 跳过隐藏文件（以 . 开头）
    - 跳过本脚本自身和整理历史日志
    - 目标重名时自动加序号（photo.png -> photo_1.png）

    by_date=True 时按 YYYY/MM 归档，否则按类别归档。
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

        folder = date_folder_for(item) if by_date else category_for(item.name, rules)
        dest = target / folder / item.name

        # 重名处理：目标已存在（磁盘上或本次规划中）则加序号
        counter = 1
        while dest.exists() or dest in planned_destinations:
            dest = target / folder / f"{item.stem}_{counter}{item.suffix}"
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
        folder = str(dest.parent.relative_to(src.parent))
        print(f"  {src.name:<30} -> {folder}/{dest.name}")

    # 按目标文件夹汇总
    counts = Counter(str(dest.parent.relative_to(src.parent)) for src, dest in moves)
    summary = ", ".join(f"{name}({n})" for name, n in sorted(counts.items()))
    print(f"\n共 {len(moves)} 个文件：{summary}")


def plan_cleanup(target: Path) -> list[Path]:
    """找出目标目录下所有空子目录，按最深优先排序（先删子目录再删父目录）。"""
    empties = [d for d in target.rglob("*") if d.is_dir() and not any(d.iterdir())]
    return sorted(empties, key=lambda d: len(d.parts), reverse=True)


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
        # 恢复后清理可能变空的归档/类别文件夹（向上回溯，直到 target 为止）
        folder = dest.parent
        while folder != target and folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
            folder = folder.parent

    # 从历史中移除该操作（已完成的移动才移除）
    if restored == len(moves):
        history.pop()
        save_history(target, history)

    print(f"已恢复 {restored}/{len(moves)} 个文件。")
    return True


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="整理文件夹中的文件：先预览，确认后 --apply 执行，--undo 可撤销。"
    )
    parser.add_argument("directory", nargs="?", default=".",
                        help="要整理的文件夹路径（默认当前目录）")
    parser.add_argument("--apply", action="store_true",
                        help="真正执行整理（默认只预览）")
    parser.add_argument("--undo", action="store_true",
                        help="撤销最近一次整理")
    parser.add_argument("--by-date", action="store_true",
                        help="按修改日期归档（YYYY/MM 文件夹），默认按类别")
    parser.add_argument("--config", metavar="FILE",
                        help="自定义分类规则 JSON 文件（与默认规则合并）")
    parser.add_argument("--clean-empty", action="store_true",
                        help="清理空文件夹（配合 --apply 执行）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.directory)

    if not target.is_dir():
        print(f"错误：目录不存在：{target}", file=sys.stderr)
        return 1

    if args.undo:
        undo_last(target)
        return 0

    # 尽早校验自定义规则，避免预览一半才发现配置有问题
    rules = load_rules(args.config)
    if rules is None:
        return 1

    print(f"目标目录：{target.resolve()}")
    print(f"模式：{'执行整理' if args.apply else '预览（不会移动任何文件）'}")
    if args.by_date:
        print("归档方式：按修改日期（YYYY/MM）")
    if args.config:
        print(f"自定义规则：{args.config}")
    print()

    moves = plan_moves(target, rules, args.by_date)
    print_plan(moves)

    empties = plan_cleanup(target) if args.clean_empty else []
    if empties:
        print(f"\n将清理 {len(empties)} 个空文件夹：")
        for d in empties:
            print(f"  {d.relative_to(target)}/")

    if not args.apply:
        if moves or empties:
            print(f"\n确认无误后，运行：python organize.py {target} --apply")
        return 0

    moved = execute_moves(target, moves) if moves else 0
    removed = 0
    todo = list(empties)  # 已按最深优先排序
    while todo:
        d = todo.pop()
        try:
            d.rmdir()
            removed += 1
            # 父目录若因此变空，加入待清理（级联）
            parent = d.parent
            if parent != target and parent.is_dir() and not any(parent.iterdir()):
                todo.append(parent)
        except OSError:
            pass  # 执行期间目录被占用或变非空，忽略

    if moved:
        print(f"\n已移动 {moved}/{len(moves)} 个文件。")
        print(f"历史记录：{target / HISTORY_NAME}（可用 --undo 撤销）")
    if removed:
        print(f"已清理 {removed} 个空文件夹。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
