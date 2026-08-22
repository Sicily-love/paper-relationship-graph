#!/usr/bin/env python3
"""Build a relocatable Python + pypdf runtime inside Paper Atlas.app."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


EXCLUDED_NAMES = {
    "Headers", "include", "share", "_CodeSignature", "site-packages",
    "__pycache__", "ensurepip", "idlelib", "lib2to3", "test", "tests",
    "tkinter", "turtledemo", "venv",
}


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in EXCLUDED_NAMES or name.endswith((".pyc", ".pyo"))
    }


def package_info(python: Path) -> dict:
    script = r"""
import importlib.metadata, importlib.util, json, pathlib
result = {}
for name in ("pypdf", "typing_extensions"):
    spec = importlib.util.find_spec(name)
    if spec is not None:
        result[name] = str(pathlib.Path(spec.origin).parent if spec.submodule_search_locations else pathlib.Path(spec.origin))
    try:
        distribution = importlib.metadata.distribution(name)
        result[name + "_dist"] = str(distribution._path)
        result[name + "_version"] = distribution.version
    except importlib.metadata.PackageNotFoundError:
        pass
print(json.dumps(result))
"""
    output = subprocess.run(
        [str(python), "-I", "-c", script], capture_output=True, text=True, check=True,
    )
    return json.loads(output.stdout)


def copy_item(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True, ignore=ignored)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def relocate_macho_files(destination: Path, version: str) -> None:
    """Rewrite Python.org's absolute framework paths for an app-local runtime."""
    prefix = f"/Library/Frameworks/Python.framework/Versions/{version}/"
    macho_files: list[Path] = []
    for item in destination.rglob("*"):
        if not item.is_file() or item.is_symlink():
            continue
        kind = subprocess.run(
            ["file", "-b", str(item)], capture_output=True, text=True, check=False,
        ).stdout
        if "Mach-O" not in kind:
            continue
        macho_files.append(item)
        dependencies = subprocess.run(
            ["otool", "-L", str(item)], capture_output=True, text=True, check=True,
        ).stdout.splitlines()[1:]
        for line in dependencies:
            dependency = line.strip().split(" (", 1)[0]
            if not dependency.startswith(prefix):
                continue
            target = destination / dependency.removeprefix(prefix)
            relative = os.path.relpath(target, item.parent)
            replacement = f"@loader_path/{relative}"
            subprocess.run(
                ["install_name_tool", "-change", dependency, replacement, str(item)],
                capture_output=True, text=True, check=True,
            )
        own_id = subprocess.run(
            ["otool", "-D", str(item)], capture_output=True, text=True, check=False,
        ).stdout.splitlines()[1:]
        if own_id and own_id[0].strip().startswith(prefix):
            subprocess.run(
                ["install_name_tool", "-id", f"@loader_path/{item.name}", str(item)],
                capture_output=True, text=True, check=True,
            )
    # Python.org's files arrive Developer ID signed. Rewriting load commands
    # invalidates those signatures, so make the whole embedded runtime internally
    # consistent before probing it. build_app.sh signs the final app afterwards.
    for item in macho_files:
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(item)],
            capture_output=True, text=True, check=True,
        )


def embed_runtime(source: Path, destination: Path, package_python: Path, source_label: str) -> dict:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not (source / "bin" / "python3").exists() or not (source / "lib").is_dir():
        raise ValueError(f"Python 运行时目录无效：{source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=True, ignore=ignored)

    library_dirs = sorted((destination / "lib").glob("python3.*"))
    if len(library_dirs) != 1:
        raise ValueError("无法确定内置 Python 的标准库版本")
    runtime_version = library_dirs[0].name.removeprefix("python")
    relocate_macho_files(destination, runtime_version)
    site_packages = library_dirs[0] / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    packages = package_info(package_python)
    if "pypdf" not in packages or "pypdf_dist" not in packages:
        raise ValueError("构建环境缺少 pypdf，请先安装 requirements.txt")
    for key in ("pypdf", "pypdf_dist", "typing_extensions", "typing_extensions_dist"):
        value = packages.get(key)
        if not value:
            continue
        source_path = Path(value)
        copy_item(source_path, site_packages / source_path.name)

    python = destination / "bin" / "python3"
    probe = subprocess.run(
        [str(python), "-I", "-B", "-c", "import json, ssl, pypdf; print(pypdf.__version__)"],
        cwd="/tmp",
        env={"HOME": "/tmp", "PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode:
        raise RuntimeError(f"内置 Python 自检失败：{probe.stderr.strip()}")
    architectures = subprocess.run(
        ["lipo", "-archs", str(python)], capture_output=True, text=True, check=False,
    ).stdout.split()
    version = subprocess.run(
        [str(python), "-I", "-B", "-c", "import platform; print(platform.python_version())"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    manifest = {
        "python_version": version,
        "pypdf_version": packages["pypdf_version"],
        "architectures": architectures,
        "source": source_label,
        "offline_ready": True,
    }
    (destination / "paper-atlas-runtime.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--package-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--source-label", default="local universal2 Python runtime")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = embed_runtime(
        args.source, args.destination, args.package_python, args.source_label,
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
