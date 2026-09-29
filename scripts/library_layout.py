#!/usr/bin/env python3
"""Canonical filesystem layout and paper discovery for the local library."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


PAPER_EXTENSIONS = frozenset({".pdf", ".pptx"})
REMOVED_LIBRARY_DIR = ".paper-atlas-removed"
ARCHIVE_LIBRARY_DIR = "_归档"
LIBRARY_ARCHIVE_DIRS = frozenset({REMOVED_LIBRARY_DIR, ARCHIVE_LIBRARY_DIR})

STANDARD_CATEGORIES = (
    "01_模型架构与基础组件",
    "02_训练方法与优化器",
    "03_训练动力学与模型分析",
    "04_长上下文与高效注意力",
    "05_MoE与稀疏模型",
    "06_量化与低精度计算",
    "07_分布式训练与数据基础设施",
    "08_GPU内核_编译器与性能工程",
    "09_GPU内核智能体与自动调优",
    "10_通用智能体与自主发现",
    "11_生成模型与视频系统",
    "12_大模型技术报告与推理训练",
    "13_个人兴趣与跨领域",
)


def is_ignored_library_path(path: Path, papers_dir: Path) -> bool:
    """Return whether a path belongs to an archive or hidden runtime folder."""
    try:
        relative = path.resolve().relative_to(papers_dir.expanduser().resolve())
    except ValueError:
        return True
    return any(part in LIBRARY_ARCHIVE_DIRS or part.startswith(".") for part in relative.parts[:-1])


def paper_files(papers_dir: Path, *, excluded_roots: Iterable[Path] = ()) -> list[Path]:
    """Return active PDF/PPTX files while excluding app code and archive folders."""
    root = papers_dir.expanduser().resolve()
    excluded = tuple(path.expanduser().resolve() for path in excluded_roots)
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in PAPER_EXTENSIONS
        and not any(path == excluded_root or excluded_root in path.parents for excluded_root in excluded)
        and not is_ignored_library_path(path, root)
    )


def is_standard_location(path: Path, papers_dir: Path) -> bool:
    root = papers_dir.expanduser().resolve()
    resolved = path.expanduser().resolve()
    return resolved.parent.parent == root and resolved.parent.name in STANDARD_CATEGORIES


def partition_by_taxonomy(papers_dir: Path, *, excluded_roots: Iterable[Path] = ()) -> tuple[list[Path], list[Path]]:
    """Split active paper files into standard-category and unclassified paths."""
    recognized: list[Path] = []
    unclassified: list[Path] = []
    for path in paper_files(papers_dir, excluded_roots=excluded_roots):
        (recognized if is_standard_location(path, papers_dir) else unclassified).append(path)
    return recognized, unclassified
