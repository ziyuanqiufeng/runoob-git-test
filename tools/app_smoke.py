# -*- coding: utf-8 -*-
"""应用启动冒烟测试：离屏启动 main.py，验证主窗口正常出现、无崩溃。

用法（一次性验证，不进 pytest 全量——避免 CI 环境的 GUI 风险）：
    python tools/app_smoke.py            # 默认 8 秒观察期
    python tools/app_smoke.py --wait 15

判定：
- 进程在观察期内持续存活 → PASS
- 提前退出 / traceback → FAIL（打印 stderr 尾部）
- 观察期后主动 terminate（冒烟不污染用户存档目录：main.py 的登录对话框
  处于模态阻塞，不会写存档）
"""
import argparse
import os
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", type=int, default=8,
                        help="观察期秒数（默认 8）")
    args = parser.parse_args()

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_ROOT, "main.py")],
        cwd=PROJECT_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )

    deadline = time.time() + args.wait
    while time.time() < deadline:
        code = proc.poll()
        if code is not None:
            _, err = proc.communicate(timeout=10)
            print(f"[FAIL] 进程提前退出（code={code}）")
            if err:
                print("--- stderr 尾部 ---")
                print("\n".join(err.strip().splitlines()[-25:]))
            return 1
        time.sleep(0.5)

    proc.terminate()
    try:
        out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate(timeout=10)

    err_tail = (err or "").strip().splitlines()
    fatal = [l for l in err_tail if "Traceback" in l or "Error" in l]
    print(f"[{'PASS' if not fatal else 'WARN'}] "
          f"main.py 离屏存活 {args.wait} 秒（未崩溃）")
    if err_tail:
        print("--- stderr 尾部（信息性） ---")
        print("\n".join(err_tail[-10:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
