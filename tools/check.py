# -*- coding: utf-8 -*-
"""一条命令跑完整验证:先测试基准,再改动审计。

用法:
    .\\.venv\\Scripts\\python.exe tools\\check.py               # 测试 + 审计(默认)
    .\\.venv\\Scripts\\python.exe tools\\check.py --gui         # 追加真窗口冒烟
    .\\.venv\\Scripts\\python.exe tools\\check.py --base HEAD~1 # 审计对照某个提交
    .\\.venv\\Scripts\\python.exe tools\\check.py --no-audit    # 只跑测试

退出码:任一步失败即非 0(可直接接进 CI / 提交前钩子)。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")

# 允许执行的脚本全部来自这里的白名单,命令一律以参数列表形式传参,不经过 shell。
ALLOWED_SCRIPTS = {
    "pytest": ["-m", "pytest"],
    "gui_smoke": ["tools/gui_smoke.py"],
    "audit": ["tools/audit_changes.py"],
}


def run(title: str, script: str, extra: list) -> tuple:
    """执行白名单脚本。subprocess 用参数列表 + shell=False,不做任何字符串拼接。"""
    base = ALLOWED_SCRIPTS.get(script)
    if base is None:
        print(f"拒绝执行非白名单脚本:{script}", file=sys.stderr)
        return 2, 0.0
    for item in extra:
        if not isinstance(item, str):
            print(f"参数必须是字符串:{item!r}", file=sys.stderr)
            return 2, 0.0

    cmd = [PY] + list(base) + list(extra)
    print("\n" + "=" * 78)
    print(f"▶ {title}")
    print("=" * 78 + f"\n$ {' '.join(cmd)}", flush=True)
    t0 = time.time()
    try:
        code = subprocess.run(cmd, cwd=str(ROOT), shell=False,
                              check=False).returncode
    except OSError as exc:
        print(f"启动失败:{exc}", file=sys.stderr)
        code = 2
    dt = time.time() - t0
    print(f"—— {title} 结束:退出码 {code},耗时 {dt:.1f}s", flush=True)
    return code, dt


def main() -> int:
    ap = argparse.ArgumentParser(description="测试基准 + 改动审计")
    ap.add_argument("--gui", action="store_true", help="追加真窗口冒烟(会短暂弹窗)")
    ap.add_argument("--base", default="HEAD", help="审计对照的 git 基准")
    ap.add_argument("--no-audit", action="store_true", help="只跑测试")
    ap.add_argument("--no-test", action="store_true", help="只跑审计")
    ap.add_argument("-k", dest="keyword", default="", help="只跑匹配该关键字的用例")
    args = ap.parse_args()

    if not Path(PY).exists():
        print(f"找不到项目虚拟环境:{PY}", file=sys.stderr)
        return 2

    results = []
    if not args.no_test:
        extra = ["tests", "-q"]
        if args.keyword:
            extra += ["-k", args.keyword]
        code, dt = run("测试基准(pytest)", "pytest", extra)
        results.append(("测试基准", code, dt))

    if args.gui:
        code, dt = run("真窗口冒烟(会短暂弹窗)", "gui_smoke", [])
        results.append(("真窗口冒烟", code, dt))

    if not args.no_audit:
        code, dt = run("改动审计", "audit", ["--base", args.base])
        results.append(("改动审计", code, dt))

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    failed = 0
    for name, code, dt in results:
        mark = "PASS" if code == 0 else "FAIL"
        if code != 0:
            failed += 1
        print(f"  [{mark}] {name}({dt:.1f}s,退出码 {code})")
    if failed:
        print(f"\n有 {failed} 项未通过:请先处理 BLOCK/WARN 再提交。")
    else:
        print("\n全部通过。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
