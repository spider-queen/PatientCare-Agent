from scripts.benchmark_agent import build_report


def test_benchmark_report_calculates_acceleration_delta():
    results = [
        {
            "name": "profile",
            "category": "high_frequency",
            "status": "success",
            "http_elapsed_ms": 120,
            "accelerated": True,
            "execution_mode": "high_frequency_acceleration",
            "tool_count": 2,
        },
        {
            "name": "complex",
            "category": "agent_orchestration",
            "status": "success",
            "http_elapsed_ms": 620,
            "accelerated": False,
            "execution_mode": "agent",
            "tool_count": 4,
        },
    ]

    report = build_report(results=results, ops_overview={})

    assert report["summary"]["success_rate"] == 100.0
    assert report["summary"]["high_frequency_acceleration_hit_rate"] == 50.0
    assert report["summary"]["accelerated_avg_http_elapsed_ms"] == 120
    assert report["summary"]["non_accelerated_avg_http_elapsed_ms"] == 620
    assert report["summary"]["acceleration_latency_delta_ms"] == 500
    assert report["by_category"]["high_frequency"]["acceleration_hit_rate"] == 100.0


def test_benchmark_report_builds_mode_comparison_summary():
    results = [
        {
            "name": "latest_visit_standard",
            "category": "high_frequency",
            "status": "success",
            "http_elapsed_ms": 100,
            "accelerated": True,
            "execution_mode": "high_frequency_acceleration",
            "tool_count": 2,
            "benchmark_mode": "accelerated",
        },
        {
            "name": "latest_visit_standard",
            "category": "high_frequency",
            "status": "success",
            "http_elapsed_ms": 400,
            "accelerated": False,
            "execution_mode": "agent",
            "tool_count": 2,
            "benchmark_mode": "forced_full_agent",
        },
    ]

    report = build_report(
        results=results,
        ops_overview={},
        case_set="high_frequency",
        compare_modes=True,
    )

    assert report["comparison"]["accelerated_avg_http_elapsed_ms"] == 100
    assert report["comparison"]["forced_full_agent_avg_http_elapsed_ms"] == 400
    assert report["comparison"]["latency_delta_ms"] == 300
    assert report["comparison"]["latency_reduction_pct"] == 75.0
    assert (
        report["comparison"]["per_case"]["latest_visit_standard"]["latency_reduction_pct"] == 75.0
    )
