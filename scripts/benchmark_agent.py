from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
REPORT_DIR = Path("reports")


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    category: str
    query: str
    expected_accelerated: bool


BENCHMARK_CASES = [
    BenchmarkCase(
        name="latest_visit_standard",
        category="high_frequency",
        query="Please summarize the latest visit for patient P0001.",
        expected_accelerated=True,
    ),
    BenchmarkCase(
        name="patient_profile_standard",
        category="high_frequency",
        query="Please show the patient profile for P0001.",
        expected_accelerated=True,
    ),
    BenchmarkCase(
        name="medical_case_standard",
        category="high_frequency",
        query="Please provide the medical case summary for P0001.",
        expected_accelerated=True,
    ),
    BenchmarkCase(
        name="latest_visit_department_constrained",
        category="constrained_query",
        query="Please summarize the latest gastroenterology follow-up visit for P0001.",
        expected_accelerated=False,
    ),
    BenchmarkCase(
        name="medication_reminder",
        category="agent_orchestration",
        query="Please help me review the latest medication reminders for P0001.",
        expected_accelerated=False,
    ),
    BenchmarkCase(
        name="memory_preference",
        category="memory_context",
        query=(
            "Please summarize the recent health concerns for P0001 using the patient's "
            "preferred response style."
        ),
        expected_accelerated=False,
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PatientCare-Agent benchmarks and write JSON/Markdown reports."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output-dir", default=str(REPORT_DIR))
    parser.add_argument(
        "--case-set",
        choices=["all", "high_frequency"],
        default="all",
        help="Choose all benchmark cases or only the low-cost high-frequency subset.",
    )
    parser.add_argument(
        "--compare-modes",
        action="store_true",
        help=(
            "For accelerated high-frequency cases, run both accelerated mode and forced "
            "full-agent mode to measure the latency delta."
        ),
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_cases = select_cases(args.case_set)
    results: list[dict[str, Any]] = []
    for round_index in range(args.repeat):
        for case in selected_cases:
            results.append(
                run_case(
                    base_url=args.base_url.rstrip("/"),
                    case=case,
                    timeout=args.timeout,
                    round_index=round_index + 1,
                    benchmark_mode=(
                        "accelerated" if args.compare_modes and case.expected_accelerated else "standard"
                    ),
                    force_full_agent=False,
                )
            )
            if args.compare_modes and case.expected_accelerated:
                results.append(
                    run_case(
                        base_url=args.base_url.rstrip("/"),
                        case=case,
                        timeout=args.timeout,
                        round_index=round_index + 1,
                        benchmark_mode="forced_full_agent",
                        force_full_agent=True,
                    )
                )

    ops_overview = fetch_json(
        f"{args.base_url.rstrip('/')}/api/dashboard/agent-ops?limit=100&recent_limit=10",
        timeout=args.timeout,
    )
    report = build_report(
        results=results,
        ops_overview=ops_overview,
        case_set=args.case_set,
        compare_modes=args.compare_modes,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    compare_suffix = "_compare" if args.compare_modes else ""
    json_path = output_dir / f"agent_benchmark_{args.case_set}{compare_suffix}_{timestamp}.json"
    md_path = output_dir / f"agent_benchmark_{args.case_set}{compare_suffix}_{timestamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")

    print(f"Benchmark completed: {len(results)} requests")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


def select_cases(case_set: str) -> list[BenchmarkCase]:
    if case_set == "high_frequency":
        return [case for case in BENCHMARK_CASES if case.category == "high_frequency"]
    return list(BENCHMARK_CASES)


def run_case(
    *,
    base_url: str,
    case: BenchmarkCase,
    timeout: int,
    round_index: int,
    benchmark_mode: str,
    force_full_agent: bool,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    payload = {
        "query": case.query,
        "images": [],
        "debug_planner": True,
        "force_full_agent": force_full_agent,
    }
    try:
        response = post_json(f"{base_url}/api/agent/query", payload, timeout=timeout)
        status = "success"
        error = None
    except Exception as exc:
        response = {}
        status = "error"
        error = str(exc)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000)
    trace = response.get("execution_trace") or {}
    runtime = trace.get("runtime") or response.get("runtime_metrics") or {}
    execution_mode = runtime.get("execution_mode") or (
        "high_frequency_acceleration" if trace.get("fast_path") else "agent"
    )
    if execution_mode == "fast_path":
        execution_mode = "high_frequency_acceleration"

    return {
        "round": round_index,
        "name": case.name,
        "category": case.category,
        "query": case.query,
        "expected_accelerated": case.expected_accelerated,
        "benchmark_mode": benchmark_mode,
        "force_full_agent": force_full_agent,
        "status": status,
        "error": error,
        "http_elapsed_ms": elapsed_ms,
        "reported_total_duration_ms": runtime.get("total_duration_ms"),
        "execution_mode": execution_mode,
        "accelerated": bool(
            trace.get("fast_path") or execution_mode == "high_frequency_acceleration"
        ),
        "tool_count": len(response.get("tool_outputs") or []),
        "run_id": response.get("run_id"),
    }


def post_json(url: str, payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    return fetch_json(request, timeout=timeout)


def fetch_json(url_or_request, *, timeout: int) -> dict[str, Any]:
    try:
        with urlopen(url_or_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to reach benchmark target: {exc}") from exc


def build_report(
    *,
    results: list[dict[str, Any]],
    ops_overview: dict[str, Any],
    case_set: str = "all",
    compare_modes: bool = False,
) -> dict[str, Any]:
    successful = [item for item in results if item["status"] == "success"]
    accelerated = [item for item in successful if item["accelerated"]]
    non_accelerated = [item for item in successful if not item["accelerated"]]
    durations = [item["http_elapsed_ms"] for item in successful]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "case_set": case_set,
        "compare_modes": compare_modes,
        "case_count": len(results),
        "success_count": len(successful),
        "summary": {
            "success_rate": rate(len(successful), len(results)),
            "high_frequency_acceleration_hit_rate": rate(len(accelerated), len(successful)),
            "avg_http_elapsed_ms": average(durations),
            "p50_http_elapsed_ms": percentile(durations, 50),
            "p95_http_elapsed_ms": percentile(durations, 95),
            "accelerated_avg_http_elapsed_ms": average(
                item["http_elapsed_ms"] for item in accelerated
            ),
            "non_accelerated_avg_http_elapsed_ms": average(
                item["http_elapsed_ms"] for item in non_accelerated
            ),
            "acceleration_latency_delta_ms": (
                average(item["http_elapsed_ms"] for item in non_accelerated)
                - average(item["http_elapsed_ms"] for item in accelerated)
                if accelerated and non_accelerated
                else 0
            ),
        },
        "by_category": summarize_by_category(successful),
        "by_benchmark_mode": summarize_by_benchmark_mode(successful),
        "comparison": summarize_comparison(successful),
        "ops_overview": ops_overview,
        "results": results,
    }


def summarize_by_category(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        grouped.setdefault(item["category"], []).append(item)
    return {
        category: {
            "case_count": len(items),
            "avg_http_elapsed_ms": average(item["http_elapsed_ms"] for item in items),
            "p95_http_elapsed_ms": percentile(
                [item["http_elapsed_ms"] for item in items],
                95,
            ),
            "acceleration_hit_rate": rate(
                sum(1 for item in items if item["accelerated"]),
                len(items),
            ),
        }
        for category, items in grouped.items()
    }


def summarize_by_benchmark_mode(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        mode = item.get("benchmark_mode", "standard")
        grouped.setdefault(mode, []).append(item)
    return {
        mode: {
            "case_count": len(items),
            "avg_http_elapsed_ms": average(item["http_elapsed_ms"] for item in items),
            "p95_http_elapsed_ms": percentile(
                [item["http_elapsed_ms"] for item in items],
                95,
            ),
            "acceleration_hit_rate": rate(
                sum(1 for item in items if item["accelerated"]),
                len(items),
            ),
        }
        for mode, items in grouped.items()
    }


def summarize_comparison(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    accelerated_runs = [item for item in results if item.get("benchmark_mode") == "accelerated"]
    forced_runs = [item for item in results if item.get("benchmark_mode") == "forced_full_agent"]
    if not accelerated_runs or not forced_runs:
        return None

    per_case: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        grouped.setdefault(item["name"], []).append(item)

    for case_name, items in grouped.items():
        case_accelerated = [item for item in items if item.get("benchmark_mode") == "accelerated"]
        case_forced = [item for item in items if item.get("benchmark_mode") == "forced_full_agent"]
        if not case_accelerated or not case_forced:
            continue
        accelerated_avg = average(item["http_elapsed_ms"] for item in case_accelerated)
        forced_avg = average(item["http_elapsed_ms"] for item in case_forced)
        per_case[case_name] = {
            "accelerated_case_count": len(case_accelerated),
            "forced_full_agent_case_count": len(case_forced),
            "accelerated_avg_http_elapsed_ms": accelerated_avg,
            "forced_full_agent_avg_http_elapsed_ms": forced_avg,
            "latency_delta_ms": forced_avg - accelerated_avg,
            "latency_reduction_pct": reduction_pct(
                baseline_ms=forced_avg,
                optimized_ms=accelerated_avg,
            ),
            "accelerated_hit_rate": rate(
                sum(1 for item in case_accelerated if item["accelerated"]),
                len(case_accelerated),
            ),
        }

    accelerated_avg = average(item["http_elapsed_ms"] for item in accelerated_runs)
    forced_avg = average(item["http_elapsed_ms"] for item in forced_runs)
    return {
        "accelerated_case_count": len(accelerated_runs),
        "forced_full_agent_case_count": len(forced_runs),
        "accelerated_avg_http_elapsed_ms": accelerated_avg,
        "forced_full_agent_avg_http_elapsed_ms": forced_avg,
        "accelerated_p95_http_elapsed_ms": percentile(
            [item["http_elapsed_ms"] for item in accelerated_runs],
            95,
        ),
        "forced_full_agent_p95_http_elapsed_ms": percentile(
            [item["http_elapsed_ms"] for item in forced_runs],
            95,
        ),
        "latency_delta_ms": forced_avg - accelerated_avg,
        "latency_reduction_pct": reduction_pct(
            baseline_ms=forced_avg,
            optimized_ms=accelerated_avg,
        ),
        "accelerated_hit_rate": rate(
            sum(1 for item in accelerated_runs if item["accelerated"]),
            len(accelerated_runs),
        ),
        "per_case": per_case,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# PatientCare-Agent Benchmark Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Case set: `{report.get('case_set', 'all')}`",
        f"- Compare modes: `{report.get('compare_modes', False)}`",
        f"- Cases: `{report['case_count']}`",
        f"- Success rate: `{summary['success_rate']}%`",
        f"- High-frequency acceleration hit rate: `{summary['high_frequency_acceleration_hit_rate']}%`",
        f"- Average latency: `{summary['avg_http_elapsed_ms']} ms`",
        f"- P50 latency: `{summary['p50_http_elapsed_ms']} ms`",
        f"- P95 latency: `{summary['p95_http_elapsed_ms']} ms`",
        f"- Accelerated average latency: `{summary['accelerated_avg_http_elapsed_ms']} ms`",
        f"- Non-accelerated average latency: `{summary['non_accelerated_avg_http_elapsed_ms']} ms`",
        f"- Acceleration latency delta: `{summary['acceleration_latency_delta_ms']} ms`",
    ]

    comparison = report.get("comparison")
    if comparison is not None:
        lines.extend(
            [
                "",
                "## Mode Comparison",
                "",
                f"- Accelerated runs: `{comparison['accelerated_case_count']}`",
                f"- Forced full-agent runs: `{comparison['forced_full_agent_case_count']}`",
                f"- Accelerated average latency: `{comparison['accelerated_avg_http_elapsed_ms']} ms`",
                f"- Forced full-agent average latency: `{comparison['forced_full_agent_avg_http_elapsed_ms']} ms`",
                f"- Accelerated P95 latency: `{comparison['accelerated_p95_http_elapsed_ms']} ms`",
                f"- Forced full-agent P95 latency: `{comparison['forced_full_agent_p95_http_elapsed_ms']} ms`",
                f"- Latency delta: `{comparison['latency_delta_ms']} ms`",
                f"- Latency reduction: `{comparison['latency_reduction_pct']}%`",
                f"- Accelerated hit rate: `{comparison['accelerated_hit_rate']}%`",
            ]
        )

    lines.extend(
        [
            "",
            "## By Category",
            "",
            "| Category | Cases | Avg Latency | P95 Latency | Acceleration Hit Rate |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for category, item in report["by_category"].items():
        lines.append(
            f"| {category} | {item['case_count']} | {item['avg_http_elapsed_ms']} ms | "
            f"{item['p95_http_elapsed_ms']} ms | {item['acceleration_hit_rate']}% |"
        )

    if report.get("by_benchmark_mode"):
        lines.extend(
            [
                "",
                "## By Benchmark Mode",
                "",
                "| Mode | Cases | Avg Latency | P95 Latency | Acceleration Hit Rate |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for mode, item in report["by_benchmark_mode"].items():
            lines.append(
                f"| {mode} | {item['case_count']} | {item['avg_http_elapsed_ms']} ms | "
                f"{item['p95_http_elapsed_ms']} ms | {item['acceleration_hit_rate']}% |"
            )

    if comparison is not None and comparison["per_case"]:
        lines.extend(
            [
                "",
                "## Per Case Comparison",
                "",
                "| Case | Accelerated Avg | Forced Full-Agent Avg | Delta | Reduction | Hit Rate |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for case_name, item in comparison["per_case"].items():
            lines.append(
                f"| {case_name} | {item['accelerated_avg_http_elapsed_ms']} ms | "
                f"{item['forced_full_agent_avg_http_elapsed_ms']} ms | "
                f"{item['latency_delta_ms']} ms | {item['latency_reduction_pct']}% | "
                f"{item['accelerated_hit_rate']}% |"
            )

    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| Case | Benchmark Mode | Category | Status | Mode | Latency | Tools |",
            "|---|---|---|---|---|---:|---:|",
        ]
    )
    for item in report["results"]:
        lines.append(
            f"| {item['name']} | {item['benchmark_mode']} | {item['category']} | "
            f"{item['status']} | {item['execution_mode']} | {item['http_elapsed_ms']} ms | "
            f"{item['tool_count']} |"
        )
    return "\n".join(lines) + "\n"


def average(values) -> int:
    materialized = [int(value) for value in values if value is not None]
    if not materialized:
        return 0
    return round(statistics.mean(materialized))


def percentile(values: list[int], pct: int) -> int:
    materialized = sorted(int(value) for value in values if value is not None)
    if not materialized:
        return 0
    index = min(round((pct / 100) * (len(materialized) - 1)), len(materialized) - 1)
    return materialized[index]


def rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def reduction_pct(*, baseline_ms: int, optimized_ms: int) -> float:
    if baseline_ms <= 0:
        return 0.0
    return round(((baseline_ms - optimized_ms) / baseline_ms) * 100, 1)


if __name__ == "__main__":
    main()
