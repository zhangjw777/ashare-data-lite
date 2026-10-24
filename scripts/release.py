"""验证发行包并创建不可变版本标签；推送后由 GitHub Actions 发布到 PyPI。"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import urlopen

from validate_release import ROOT, project_version, validate


def git(*args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def release(version, check_only=False):
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise RuntimeError("版本号使用 X.Y.Z 格式")
    if git("status", "--porcelain"):
        raise RuntimeError("请先审阅并提交代码改动，再执行发布命令")
    branch = git("branch", "--show-current")
    if branch != "main":
        raise RuntimeError("发布命令在 main 分支执行")
    git("fetch", "origin", "--tags")
    if (
        not subprocess.run(
            ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"], cwd=ROOT
        ).returncode
        == 0
    ):
        raise RuntimeError("请先整合 origin/main 的最新提交")
    tag = f"v{version}"
    if tag in git("tag", "--list").splitlines():
        raise RuntimeError(f"版本标签已存在：{tag}，请选择新版本")
    try:
        with urlopen(
            "https://pypi.org/pypi/ashare-data-lite/json", timeout=15
        ) as response:
            versions = json.load(response)["releases"]
    except HTTPError as exc:
        if exc.code != 404:
            raise
        versions = {}
    if version in versions:
        raise RuntimeError(f"PyPI 版本已存在：{version}")
    stable = [
        tuple(map(int, item.split(".")))
        for item in versions
        if re.fullmatch(r"\d+\.\d+\.\d+", item)
    ]
    if stable and tuple(map(int, version.split("."))) <= max(stable):
        raise RuntimeError("新版本应高于当前 PyPI 稳定版本")
    file = ROOT / "src" / "ashare_data" / "__init__.py"
    previous = file.read_text(encoding="utf-8")
    changed = version != project_version()
    if changed:
        file.write_text(
            re.sub(
                r'^__version__ = "[^"]+"',
                f'__version__ = "{version}"',
                previous,
                count=1,
                flags=re.MULTILINE,
            ),
            encoding="utf-8",
        )
    try:
        with tempfile.TemporaryDirectory(prefix="ashare-release-") as directory:
            validate(Path(directory) / "dist")
    except BaseException:
        if changed:
            file.write_text(previous, encoding="utf-8")
        raise
    if check_only:
        if changed:
            file.write_text(previous, encoding="utf-8")
        print("PASS release preflight")
        return
    if changed:
        git("add", "src/ashare_data/__init__.py")
        git("commit", "-m", f"Release {version}")
    git("push", "origin", "HEAD:main")
    git("tag", "-a", tag, "-m", f"ashare-data-lite {version}")
    git("push", "origin", f"refs/tags/{tag}")
    print(
        "已触发发布：https://github.com/zhangjw777/ashare-data-lite/actions/workflows/publish.yml"
    )
    print(
        f"发布后验证：python -m pip install --index-url https://pypi.org/simple ashare-data-lite=={version}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        release(args.version, args.check_only)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"发布中止：{exc}", file=sys.stderr)
        raise SystemExit(1)
