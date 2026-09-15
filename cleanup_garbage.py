# -*- coding: utf-8 -*-
"""项目垃圾文件清理脚本。

用法：
    python cleanup_garbage.py            # 清理 A/B/C 三组（缓存+探测垃圾+测试备份）
    python cleanup_garbage.py --dry-run  # 仅预览，不删除
    python cleanup_garbage.py --with-outputs  # 连同 outputs/ 历史产物一起清理

说明：
- A 组：__pycache__ / .pyc / .pytest_cache —— 纯缓存，删后自动再生成
- B 组：探测/误创建的零字节残留 —— 无任何引用
- C 组：根目录 backups/ —— 测试运行时滚动备份机制的产物，下次跑测试会再生成
- D 组：outputs/ —— 历史工作产物（UI 截图/地图渲染/城市预览），游戏不读取，仅作参考

绝不触碰：.venv / .workbuddy / .github / .gitignore / assets / config / docs /
game / tests / tools / ui / saves（正式存档）/ main.py / requirements.txt 等。
"""
import argparse
import glob
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 完全不深入的目录（内部的缓存/文件一律不碰）
SKIP_ENTIRELY = {".venv", ".workbuddy", ".github", "backups", "outputs"}

# 绝对不触碰（文档性说明；删除目标均为缓存/残留，与下列无关）
PROTECTED = {
    ".venv", ".workbuddy", ".github", ".gitignore",
    "assets", "config", "docs", "game", "tests", "tools", "ui",
    "saves", "main.py", "generate_manual.py", "requirements.txt",
    "cleanup_garbage.py",
}


def _iter_pycache_dirs():
    """遍历项目（跳过完全不深入的目录），收集所有 __pycache__ 目录。

    注意：game/tests/ui/tools 等源码目录本身不跳过——它们的 __pycache__
    正是主要收集对象；只把 __pycache__ 自身加入结果且不深入其内部。
    """
    result = []
    for dirpath, dirnames, _ in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        top = rel.split(os.sep)[0] if rel != "." else ""
        if top in SKIP_ENTIRELY:
            dirnames[:] = []
            continue
        # 先收集本层的 __pycache__
        for d in list(dirnames):
            if d == "__pycache__":
                result.append(os.path.join(dirpath, d))
        # 再剪枝：不深入 __pycache__ 内部，也不进入完全保护区
        dirnames[:] = [d for d in dirnames
                       if d != "__pycache__" and d not in SKIP_ENTIRELY]
    return result


def _dir_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _remove_dir(path, dry, deleted):
    size = _dir_size(path)
    if dry:
        print(f"[预览] 将删除目录 {os.path.relpath(path, ROOT)}  ({size/1024:.0f} KB)")
    else:
        try:
            shutil.rmtree(path)
            print(f"[已删] 目录 {os.path.relpath(path, ROOT)}  ({size/1024:.0f} KB)")
        except OSError as e:
            print(f"[失败] {os.path.relpath(path, ROOT)}: {e}")
            return 0
    deleted += size
    return deleted


def _remove_file(path, dry, deleted):
    if not os.path.exists(path):
        return deleted
    size = os.path.getsize(path)
    rel = os.path.relpath(path, ROOT)
    if dry:
        print(f"[预览] 将删除文件 {rel}  ({size} B)")
    else:
        try:
            os.remove(path)
            print(f"[已删] 文件 {rel}  ({size} B)")
        except OSError as e:
            print(f"[失败] {rel}: {e}")
            return deleted
    deleted += size
    return deleted


def collect_targets(include_outputs):
    """返回 (缓存目录列表, 待删文件列表, 可选目录列表, 测试备份目录)。"""
    cache_dirs = _iter_pycache_dirs()
    if os.path.isdir(os.path.join(ROOT, ".pytest_cache")):
        cache_dirs.append(os.path.join(ROOT, ".pytest_cache"))
    junk_files = list(glob.glob(os.path.join(ROOT, "180000*")))  # 命令误创建的空文件
    junk_files += [
        os.path.join(ROOT, "saves", "_probe_delete_test.json"),
        os.path.join(ROOT, "saves", "_probe_replace.json"),
        os.path.join(ROOT, "collect_list.txt"),   # pytest 收集定位临时文件
        os.path.join(ROOT, "run_log.txt"),        # 测试挂点排查日志
        os.path.join(ROOT, "subset.txt"),         # 二分定位临时文件
    ]
    optional_dirs = []
    if include_outputs and os.path.isdir(os.path.join(ROOT, "outputs")):
        optional_dirs.append(os.path.join(ROOT, "outputs"))
    test_backups = os.path.join(ROOT, "backups")
    return cache_dirs, junk_files, optional_dirs, test_backups


def main():
    parser = argparse.ArgumentParser(description="问道长生 · 垃圾文件清理")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不删除")
    parser.add_argument("--with-outputs", action="store_true",
                        help="连同 outputs/ 历史工作产物一起清理")
    args = parser.parse_args()

    cache_dirs, junk_files, optional_dirs, test_backups = collect_targets(args.with_outputs)

    print("=" * 56)
    print("问道长生 · 垃圾文件清理" + ("（预览模式）" if args.dry_run else ""))
    print("=" * 56)

    deleted = 0
    print(f"\n—— A 组：编译/测试缓存（{len(cache_dirs)} 项，删后自动再生成）——")
    for d in cache_dirs:
        deleted = _remove_dir(d, args.dry_run, deleted)

    print("\n—— B 组：探测/误创建残留 ——")
    for f in junk_files:
        deleted = _remove_file(f, args.dry_run, deleted)

    print("\n—— C 组：测试运行产物 backups/（下次跑测试会再生成）——")
    if os.path.isdir(test_backups):
        deleted = _remove_dir(test_backups, args.dry_run, deleted)
    else:
        print("[跳过] 不存在")

    if optional_dirs:
        print("\n—— D 组：outputs/ 历史工作产物 ——")
        for d in optional_dirs:
            deleted = _remove_dir(d, args.dry_run, deleted)
    else:
        print("\n—— D 组：outputs/ 未包含（如需清理请加 --with-outputs）——")

    print("\n" + "=" * 56)
    print(f"合计释放空间：{deleted/1024/1024:.2f} MB")
    if args.dry_run:
        print("当前为预览模式，未实际删除。")
    print("完成。")


if __name__ == "__main__":
    sys.exit(main())
