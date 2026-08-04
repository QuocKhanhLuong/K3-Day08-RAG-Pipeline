"""Evaluate two RAG configurations with RAGAS and export Markdown results."""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DATASET_PATH = Path(__file__).with_name("golden_dataset.json")
RESULTS_PATH = Path(__file__).with_name("results.md")
METRICS = ("faithfulness", "answer_relevancy", "context_recall", "context_precision")


def load_golden_dataset() -> list[dict[str, Any]]:
    data = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 15:
        raise ValueError("golden_dataset.json phải chứa đúng 15 câu hỏi")
    required = {"question", "expected_answer", "expected_context"}
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError(f"Mẫu #{index} thiếu trường bắt buộc: {sorted(required)}")
    return data


def _ragas_runtime():
    """Build evaluator LLM/embeddings for either OpenAI or OpenRouter."""
    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    except ImportError as error:
        raise RuntimeError("Thiếu dependencies; chạy: pip install -r requirements.txt") from error

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Cần đặt OPENAI_API_KEY hoặc OPENROUTER_API_KEY để RAGAS chấm điểm")

    openrouter = bool(os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"))
    base_url = os.getenv("OPENAI_BASE_URL")
    if openrouter:
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    model = os.getenv("RAGAS_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    if openrouter and "/" not in model:
        model = f"openai/{model}"
    common = {"api_key": api_key}
    if base_url:
        common["base_url"] = base_url
    llm = ChatOpenAI(model=model, temperature=0, **common)

    embedding_model = os.getenv("RAGAS_EMBEDDING_MODEL", "text-embedding-3-small")
    if openrouter and "/" not in embedding_model:
        embedding_model = f"openai/{embedding_model}"
    embeddings = OpenAIEmbeddings(model=embedding_model, **common)
    return llm, embeddings


def collect_answers(
    generate: Callable[..., dict[str, Any]],
    golden_dataset: list[dict[str, Any]],
    *,
    top_k: int,
) -> dict[str, list[Any]]:
    rows: dict[str, list[Any]] = {
        "question": [], "answer": [], "contexts": [], "ground_truth": []
    }
    for index, item in enumerate(golden_dataset, 1):
        print(f"[{index:02d}/{len(golden_dataset)}] top_k={top_k}: {item['question']}", flush=True)
        output = generate(item["question"], top_k=top_k)
        rows["question"].append(item["question"])
        rows["answer"].append(output.get("answer", ""))
        rows["contexts"].append([chunk.get("content", "") for chunk in output.get("sources", [])])
        rows["ground_truth"].append(item["expected_answer"])
    return rows


def evaluate_with_ragas(eval_data: dict[str, list[Any]]) -> list[dict[str, Any]]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
        from ragas.run_config import RunConfig
    except ImportError as error:
        raise RuntimeError("Thiếu RAGAS; chạy: pip install -r requirements.txt") from error

    llm, embeddings = _ragas_runtime()
    result = evaluate(
        Dataset.from_dict(eval_data),
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(
            timeout=90,
            max_retries=2,
            max_wait=15,
            max_workers=4,
            log_tenacity=True,
        ),
        # Do not silently turn API/configuration errors into NaN scores.
        raise_exceptions=True,
    )
    return result.to_pandas().to_dict(orient="records")


def _mean(rows: list[dict[str, Any]], metric: str) -> float:
    values = []
    for row in rows:
        value = row.get(metric)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isnan(numeric):
            values.append(numeric)
    return sum(values) / len(values) if values else float("nan")


def export_results(config_rows: dict[str, list[dict[str, Any]]]) -> None:
    names = list(config_rows)
    averages = {name: {metric: _mean(rows, metric) for metric in METRICS} for name, rows in config_rows.items()}
    lines = [
        "# RAG Evaluation Results", "",
        f"- Framework: **RAGAS 0.1.21**",
        f"- Số câu hỏi: **15**",
        f"- Thời điểm chạy: **{datetime.now().astimezone().isoformat(timespec='seconds')}**", "",
        "## So sánh cấu hình", "",
        f"| Metric | {names[0]} | {names[1]} | Δ ({names[1]} - {names[0]}) |",
        "|---|---:|---:|---:|",
    ]
    for metric in METRICS:
        a, b = averages[names[0]][metric], averages[names[1]][metric]
        lines.append(f"| {metric} | {a:.4f} | {b:.4f} | {b-a:+.4f} |")
    mean_a = sum(averages[names[0]].values()) / len(METRICS)
    mean_b = sum(averages[names[1]].values()) / len(METRICS)
    lines.extend([f"| **Average** | **{mean_a:.4f}** | **{mean_b:.4f}** | **{mean_b-mean_a:+.4f}** |", ""])

    best = names[1] if mean_b > mean_a else names[0]
    lines.extend(["## Kết luận", "", f"**{best}** có điểm trung bình cao hơn trên bộ kiểm thử này.", ""])
    for name, rows in config_rows.items():
        lines.extend([f"## Chi tiết — {name}", "", "| # | Question | Faithfulness | Relevancy | Recall | Precision |", "|---:|---|---:|---:|---:|---:|"])
        for index, row in enumerate(rows, 1):
            def score(metric: str) -> str:
                try:
                    return f"{float(row.get(metric)):.4f}"
                except (TypeError, ValueError):
                    return "N/A"
            question = str(row.get("question", "")).replace("|", "\\|")
            lines.append(f"| {index} | {question} | {score('faithfulness')} | {score('answer_relevancy')} | {score('context_recall')} | {score('context_precision')} |")
        lines.append("")
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-a-top-k", type=int, default=3)
    parser.add_argument("--config-b-top-k", type=int, default=5)
    args = parser.parse_args()
    if args.config_a_top_k < 1 or args.config_b_top_k < 1:
        parser.error("top_k phải lớn hơn 0")

    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.task10_generation import generate_with_citation

    golden = load_golden_dataset()
    # Fail before the relatively expensive retrieval/generation loop when the
    # evaluator is not configured.
    _ragas_runtime()
    configs = {
        f"Config A (top_k={args.config_a_top_k})": args.config_a_top_k,
        f"Config B (top_k={args.config_b_top_k})": args.config_b_top_k,
    }
    evaluated = {}
    for name, top_k in configs.items():
        print(f"\n=== Thu thập câu trả lời: {name} ===", flush=True)
        evaluated[name] = evaluate_with_ragas(
            collect_answers(generate_with_citation, golden, top_k=top_k)
        )
        print(f"=== RAGAS đã chấm xong: {name} ===", flush=True)
    export_results(evaluated)
    print(f"Đã ghi kết quả vào {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
