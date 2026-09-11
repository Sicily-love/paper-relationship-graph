#!/usr/bin/env python3
"""Reclassify the complete Paper Atlas library into the current 13-category taxonomy."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

import build_graph


SOURCE_DEFAULTS = {
    "01_模型架构与基础组件": "01_模型架构与基础组件",
    "02_训练方法与优化器": "02_训练方法与优化器",
    "03_训练动力学与模型分析": "03_训练动力学与模型分析",
    "04_长上下文与高效注意力": "04_长上下文与高效注意力",
    "05_MoE与稀疏模型": "05_MoE与稀疏模型",
    "06_量化与低精度计算": "06_量化与低精度计算",
    "07_分布式训练与数据基础设施": "07_分布式训练与数据基础设施",
    "08_GPU内核_编译器与性能工程": "08_GPU内核_编译器与性能工程",
    "09_GPU内核智能体与自动调优": "09_GPU内核智能体与自动调优",
    "10_通用智能体与自主发现": "10_通用智能体与自主发现",
    "11_生成模型与视频系统": "11_生成模型与视频系统",
    "12_大模型技术报告与推理训练": "12_大模型技术报告与推理训练",
    "13_个人兴趣与跨领域": "13_个人兴趣与跨领域",
}

TITLE_OVERRIDES = {
    # Practical optimization and training methods.
    "Decoupled weight decay regularization": "02_训练方法与优化器",
    "Muon An optimizer for hidden layers in neural networks": "02_训练方法与优化器",
    "Muon is scalable for LLM training": "02_训练方法与优化器",
    "On-Policy Distillation": "02_训练方法与优化器",
    "Directional Consistency as a Complementary Optimization Signal The GONO Framework": "02_训练方法与优化器",
    "GAC Stabilizing Asynchronous RL Training for LLMs via Gradient Alignment Control": "02_训练方法与优化器",
    "Tensor Programs V Tuning Large Neural Networks via Zero-Shot Hyperparameter Transfer": "02_训练方法与优化器",

    # Training dynamics, diagnostics and model-behavior analysis.
    "A Scalable Measure of Loss Landscape Curvature for Analyzing the Training Dynamics of LLMs": "03_训练动力学与模型分析",
    "A Tail-Index Analysis of Stochastic Gradient Noise in Deep Neural Networks": "03_训练动力学与模型分析",
    "How Instruction and Reasoning Data shape Post-Training Data Quality through the Lens of Layer-wise Gradients": "03_训练动力学与模型分析",
    "Massive Activations in Large Language Models": "03_训练动力学与模型分析",
    "Spectral Lens Activation and Gradient Spectra as Diagnostics of LLM Optimization": "03_训练动力学与模型分析",

    # Long-context and sparse-attention algorithms.
    "Efficient streaming language models with attention sinks": "04_长上下文与高效注意力",
    "MOBA MIXTURE OF BLOCK ATTENTION FOR LONG-CONTEXT LLMS": "04_长上下文与高效注意力",
    "SpargeAttention Accurate and Training-free Sparse Attention Accelerating Any Model Inference": "04_长上下文与高效注意力",

    # Attention-specific low-precision methods.
    "Attn-QAT 4-Bit Attention With Quantization-Aware Training": "06_量化与低精度计算",
    "SageAttention Accurate 8-Bit Attention for Plug-and-play Inference Acceleration": "06_量化与低精度计算",
    "SageAttention2 Efficient Attention with Thorough Outlier Smoothing and Per-thread INT4 Quantization": "06_量化与低精度计算",
    "SageAttention3 Microscaling FP4 Attention for Inference and An Exploration of 8-Bit Training": "06_量化与低精度计算",

    # These papers study general low-precision/outlier behavior beyond attention kernels.
    "Dissecting Outlier Dynamics in LLM NVFP4 Pretraining": "06_量化与低精度计算",
    "From Attention to Activation Unravelling the Enigmas of Large Language Models": "06_量化与低精度计算",
    "AWQ Activation-aware Weight Quantization for LLM Compression and Acceleration": "06_量化与低精度计算",
    "SVDQuant Absorbing Outliers by Low-Rank Components for 4-Bit Diffusion Models": "06_量化与低精度计算",
}

PAPER_SUFFIXES = {".pdf", ".pptx"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def duplicate_path(destination: Path, reserved: set[Path]) -> Path:
    index = 1
    while True:
        marker = " (重复副本)" if index == 1 else f" (重复副本 {index})"
        candidate = destination.with_name(f"{destination.stem}{marker}{destination.suffix}")
        if not candidate.exists() and candidate not in reserved:
            return candidate
        index += 1


def source_papers(papers_dir: Path) -> list[Path]:
    papers = [
        path for path in papers_dir.iterdir()
        if path.is_file() and path.suffix.lower() in PAPER_SUFFIXES
    ]
    for folder_name in SOURCE_DEFAULTS:
        folder = papers_dir / folder_name
        if folder.is_dir():
            papers.extend(
                path for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in PAPER_SUFFIXES
            )
    return sorted(papers, key=lambda path: str(path.relative_to(papers_dir)).lower())


def destination_category(source: Path, papers_dir: Path) -> str:
    override = TITLE_OVERRIDES.get(source.stem)
    if override:
        return override
    if source.parent == papers_dir:
        raise RuntimeError(f"根目录论文缺少明确分类：{source.name}")
    category = SOURCE_DEFAULTS.get(source.parent.name)
    if not category:
        raise RuntimeError(f"无法识别来源类别：{source.relative_to(papers_dir)}")
    return category


def migration_plan(papers_dir: Path) -> tuple[list[tuple[Path, Path]], list[str]]:
    moves: list[tuple[Path, Path]] = []
    duplicates: list[str] = []
    reserved: dict[Path, str] = {}
    for source in source_papers(papers_dir):
        category = destination_category(source, papers_dir)
        requested = papers_dir / category / source.name
        if source == requested:
            continue
        destination = requested
        source_digest = digest(source)
        occupied_digest = reserved.get(destination)
        if destination.exists() and destination != source:
            occupied_digest = digest(destination)
        if occupied_digest is not None:
            if occupied_digest != source_digest:
                raise RuntimeError(f"同名文件内容不同，迁移已停止：{source} -> {destination}")
            destination = duplicate_path(destination, set(reserved))
            duplicates.append(str(destination.relative_to(papers_dir)))
        reserved[destination] = source_digest
        moves.append((source, destination))
    return moves, duplicates


def migrate(papers_dir: Path, *, dry_run: bool = False) -> tuple[Counter[str], list[str]]:
    moves, duplicates = migration_plan(papers_dir)
    counts: Counter[str] = Counter()
    for source, destination in moves:
        counts[destination.parent.name] += 1
        print(f"{'计划' if dry_run else '移动'} {source.relative_to(papers_dir)} -> {destination.relative_to(papers_dir)}")
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
    if not dry_run:
        for old_name in SOURCE_DEFAULTS:
            folder = papers_dir / old_name
            if folder.is_dir() and old_name not in build_graph.STANDARD_CATEGORIES and not any(folder.iterdir()):
                folder.rmdir()
    return counts, duplicates


def verify(papers_dir: Path) -> Counter[str]:
    categories = set(build_graph.STANDARD_CATEGORIES)
    counts: Counter[str] = Counter()
    unreadable: list[str] = []
    unclassified: list[str] = []
    for path in sorted(papers_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in PAPER_SUFFIXES:
            continue
        if build_graph.REPO_ROOT in path.parents or ".paper-atlas-removed" in path.parts:
            continue
        if path.parent.parent != papers_dir or path.parent.name not in categories:
            unclassified.append(str(path.relative_to(papers_dir)))
            continue
        counts[path.parent.name] += 1
        if path.suffix.lower() == ".pdf":
            try:
                reader = PdfReader(str(path))
                if not reader.pages:
                    raise ValueError("没有页面")
            except Exception as error:  # noqa: BLE001 - every unreadable PDF must be reported
                unreadable.append(f"{path.relative_to(papers_dir)}: {error}")
    if unclassified:
        raise RuntimeError("仍有未分类论文：\n" + "\n".join(unclassified))
    if unreadable:
        raise RuntimeError("无法读取的 PDF：\n" + "\n".join(unreadable))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers-dir", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    papers_dir = args.papers_dir.expanduser().resolve()
    moves, duplicates = migration_plan(papers_dir)
    if args.dry_run:
        for source, destination in moves:
            print(f"计划 {source.relative_to(papers_dir)} -> {destination.relative_to(papers_dir)}")
        print(f"计划迁移 {len(moves)} 个文件；重复副本 {len(duplicates)} 个")
        return 0
    migrate(papers_dir)
    counts = verify(papers_dir)
    print("迁移完成：" + "，".join(f"{category} {counts[category]}" for category in build_graph.STANDARD_CATEGORIES))
    if duplicates:
        print("保留的重复副本：" + "，".join(duplicates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
