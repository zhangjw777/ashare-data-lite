"""构建并验证发行包，可在本地和 GitHub Actions 中共同使用。"""

import argparse
import ast
import email
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST_NAME = "ashare-data-lite"
IMPORT_NAME = "ashare_data"
TOKEN_PATTERNS = (
    re.compile(r"pypi-[A-Za-z0-9_-]{40,}"),
    re.compile(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{25,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
)


def run(*args, cwd=ROOT):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def check_content(name, content):
    parts = Path(name).parts
    if any(
        part in {".git", ".venv", ".pypirc", "__pycache__"}
        or part == ".env"
        or part.startswith(".env.")
        for part in parts
    ):
        raise RuntimeError(f"发行文件包含凭据或本地环境路径：{name}")
    if name.endswith((".pem", ".key")):
        raise RuntimeError(f"发行文件包含密钥文件：{name}")
    text = content.decode("utf-8", errors="replace")
    if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
        raise RuntimeError(f"文件包含疑似凭据：{name}")


def project_version():
    text = (ROOT / "src" / IMPORT_NAME / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__ = "([^"]+)"', text, re.MULTILINE)[1]


def check_workflow():
    import yaml

    path = ROOT / ".github" / "workflows" / "publish.yml"
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert "v*" in data["on"]["push"]["tags"]
    publish = data["jobs"]["publish"]
    assert publish["needs"] == "build"
    assert publish["environment"]["name"] == "pypi"
    assert publish["permissions"]["id-token"] == "write"
    assert any(
        step.get("uses", "").startswith("pypa/gh-action-pypi-publish@")
        for step in publish["steps"]
    )
    publishers = []
    for file in path.parent.glob("*.y*ml"):
        if "pypa/gh-action-pypi-publish@" in file.read_text(encoding="utf-8"):
            publishers.append(file.name)
    assert publishers == ["publish.yml"], f"发现重复发布工作流：{publishers}"
    print("PASS workflow YAML and Trusted Publishing configuration", flush=True)


def validate(dist_dir, build=True):
    for path in [
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("tests/*.py"),
        *ROOT.glob("scripts/*.py"),
    ]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    check_workflow()
    if build:
        dist_dir.mkdir(parents=True, exist_ok=True)
        if list(dist_dir.glob("*.whl")) or list(dist_dir.glob("*.tar.gz")):
            raise RuntimeError("构建目录应为空，请选择新的 --dist-dir")
        run(sys.executable, "-m", "build", "--outdir", dist_dir)
    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, "每次发布应包含一个 wheel 和一个 sdist"
    wheel, sdist = wheels[0], sdists[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert f"{IMPORT_NAME}/__init__.py" in names
        assert f"{IMPORT_NAME}/models.py" in names
        assert f"{IMPORT_NAME}/py.typed" in names
        metadata = email.message_from_bytes(
            archive.read(next(n for n in names if n.endswith("/METADATA")))
        )
        assert metadata["Name"] == DIST_NAME
        assert metadata["Version"] == project_version()
        assert metadata["Requires-Python"] == ">=3.10"
        assert metadata["License-Expression"] == "MIT"
        assert not [
            value
            for value in metadata.get_all("Requires-Dist", [])
            if "extra ==" not in value
        ]
        for name in names:
            check_content(name, archive.read(name))
    with tarfile.open(sdist) as archive:
        members = archive.getmembers()
        assert any(
            member.name.endswith(f"src/{IMPORT_NAME}/__init__.py") for member in members
        )
        assert any(member.name.endswith("docs/api.md") for member in members)
        for member in members:
            if member.isfile():
                check_content(member.name, archive.extractfile(member).read())
    run(sys.executable, "-m", "twine", "check", "--strict", wheel, sdist)
    with tempfile.TemporaryDirectory(prefix="ashare-install-") as temp:
        temp = Path(temp)
        environment = temp / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        run(python, "-m", "pip", "install", "--no-deps", wheel, cwd=temp)
        run(
            python,
            "-I",
            "-c",
            f"import {IMPORT_NAME}; from importlib.metadata import version; "
            f"assert {IMPORT_NAME}.__version__ == version('{DIST_NAME}') == '{project_version()}'; "
            "print('PASS installed wheel import and version')",
            cwd=temp,
        )
        run(
            python,
            "-I",
            "-m",
            "unittest",
            "discover",
            "-s",
            ROOT / "tests",
            "-v",
            cwd=temp,
        )
        # 从 sdist 重建 wheel，验证源码包可以独立构建。
        run(
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            temp / "rebuilt",
            sdist,
            cwd=temp,
        )
    print(f"PASS release validation: {DIST_NAME} {project_version()}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    validate(args.dist_dir.resolve(), build=not args.skip_build)
