#!/usr/bin/env python3
"""Migrate a Paper Atlas library from the 10-category taxonomy to v1.4."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


OLD_TO_NEW = {
    "01_模型架构与训练优化": "01_模型架构与基础组件",
    "02_注意力机制与长上下文": "03_注意力机制与长上下文",
    "03_MoE与稀疏模型": "04_MoE与稀疏模型",
    "04_量化与低精度计算": "05_量化与低精度计算",
    "05_分布式训练与数据基础设施": "06_分布式训练与数据基础设施",
    "06_GPU内核_编译器与性能工程": "07_GPU内核_编译器与性能工程",
    "07_GPU内核智能体与自动调优": "08_GPU内核智能体与自动调优",
    "08_通用智能体与自主学习": "09_通用智能体与自主发现",
    "09_生成模型与视频系统": "10_生成模型与视频系统",
    "10_大模型技术报告与推理训练": "11_大模型技术报告与推理训练",
}

TITLE_OVERRIDES = {
    "Decoupled weight decay regularization": "02_训练方法与优化器",
    "Muon An optimizer for hidden layers in neural networks": "02_训练方法与优化器",
    "Muon is scalable for LLM training": "02_训练方法与优化器",
    "On-Policy Distillation": "02_训练方法与优化器",
    "Online normalizer calculation for softmax": "03_注意力机制与长上下文",
    "AIDE AI-Driven Exploration in the Space of Code": "09_通用智能体与自主发现",
    "CORAL Towards autonomous multi-agent evolution for open-ended discovery": "09_通用智能体与自主发现",
    "EvoMem Memory-Augmented Evolution for Code Optimization": "09_通用智能体与自主发现",
    "AVO Agentic Variation Operators for Autonomous Evolutionary Search": "08_GPU内核智能体与自动调优",
    "LLM4LLM Bridging Kernel Benchmarks and Real Deployment via Closed-Loop Agentic Optimization": "08_GPU内核智能体与自动调优",
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def destination_for(source: Path) -> str:
    return TITLE_OVERRIDES.get(source.stem, OLD_TO_NEW[source.parent.name])


def available_duplicate_path(destination: Path) -> Path:
    suffix = 1
    while True:
        marker = " (重复副本)" if suffix == 1 else f" (重复副本 {suffix})"
        candidate = destination.with_name(f"{destination.stem}{marker}{destination.suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def migrate(papers_dir: Path, *, dry_run: bool = False) -> tuple[Counter[str], list[str]]:
    moves: list[tuple[Path, Path]] = []
    for old_name in OLD_TO_NEW:
        source_dir = papers_dir / old_name
        if not source_dir.exists():
            continue
        for source in sorted(source_dir.iterdir()):
            if source.is_file() and source.suffix.lower() in {".pdf", ".pptx"}:
                destination = papers_dir / destination_for(source) / source.name
                moves.append((source, destination))

    counts: Counter[str] = Counter()
    duplicates: list[str] = []
    for source, requested_destination in moves:
        destination = requested_destination
        if destination.exists():
            if digest(source) != digest(destination):
                raise RuntimeError(f"同名文件内容不同，迁移已停止：{source} -> {destination}")
            destination = available_duplicate_path(destination)
            duplicates.append(str(destination.relative_to(papers_dir)))
        counts[destination.parent.name] += 1
        print(f"{'计划' if dry_run else '移动'} {source.relative_to(papers_dir)} -> {destination.relative_to(papers_dir)}")
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))

    if not dry_run:
        for old_name in OLD_TO_NEW:
            source_dir = papers_dir / old_name
            if source_dir.exists() and not any(source_dir.iterdir()):
                source_dir.rmdir()
    return counts, duplicates


def verify(papers_dir: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    unreadable: list[str] = []
    for category in set(OLD_TO_NEW.values()) | set(TITLE_OVERRIDES.values()):
        folder = papers_dir / category
        for paper in sorted(folder.glob("*.pdf")) if folder.exists() else []:
            counts[category] += 1
            try:
                reader = PdfReader(str(paper))
                if not reader.pages:
                    raise ValueError("没有页面")
            except Exception as error:  # noqa: BLE001 - report every unreadable library file
                unreadable.append(f"{paper.name}: {error}")
        if folder.exists():
            counts[category] += len(list(folder.glob("*.pptx")))
    remaining = [
        name
        for name in OLD_TO_NEW
        if (papers_dir / name).exists()
        and any(
            item.is_file() and item.suffix.lower() in {".pdf", ".pptx"}
            for item in (papers_dir / name).iterdir()
        )
    ]
    if remaining:
        raise RuntimeError(f"旧分类目录仍存在：{', '.join(remaining)}")
    if unreadable:
        raise RuntimeError("无法读取的 PDF：\n" + "\n".join(unreadable))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    counts, duplicates = migrate(papers_dir, dry_run=args.dry_run)
    if args.dry_run:
        print(f"计划迁移 {sum(counts.values())} 篇论文")
        return 0
    final_counts = verify(papers_dir)
    print("迁移完成：" + "，".join(f"{category} {count}" for category, count in sorted(final_counts.items())))
    if duplicates:
        print("保留的重复副本：" + "，".join(duplicates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
