# PatientCare-Agent Benchmark Report

- Generated at: `2026-04-24T22:07:30`
- Case set: `high_frequency`
- Compare modes: `True`
- Cases: `18`
- Success rate: `72.2%`
- High-frequency acceleration hit rate: `0.0%`
- Average latency: `96769 ms`
- P50 latency: `96721 ms`
- P95 latency: `104913 ms`
- Accelerated average latency: `0 ms`
- Non-accelerated average latency: `96769 ms`
- Acceleration latency delta: `0 ms`

## Mode Comparison

- Accelerated runs: `6`
- Forced full-agent runs: `7`
- Accelerated average latency: `98261 ms`
- Forced full-agent average latency: `95490 ms`
- Accelerated P95 latency: `108836 ms`
- Forced full-agent P95 latency: `103266 ms`
- Latency delta: `-2771 ms`
- Latency reduction: `-2.9%`
- Accelerated hit rate: `0.0%`

## By Category

| Category | Cases | Avg Latency | P95 Latency | Acceleration Hit Rate |
|---|---:|---:|---:|---:|
| high_frequency | 13 | 96769 ms | 104913 ms | 0.0% |

## By Benchmark Mode

| Mode | Cases | Avg Latency | P95 Latency | Acceleration Hit Rate |
|---|---:|---:|---:|---:|
| accelerated | 6 | 98261 ms | 108836 ms | 0.0% |
| forced_full_agent | 7 | 95490 ms | 103266 ms | 0.0% |

## Per Case Comparison

| Case | Accelerated Avg | Forced Full-Agent Avg | Delta | Reduction | Hit Rate |
|---|---:|---:|---:|---:|---:|
| latest_visit_standard | 95386 ms | 97008 ms | 1622 ms | 1.7% | 0.0% |
| patient_profile_standard | 96653 ms | 92787 ms | -3866 ms | -4.2% | 0.0% |
| medical_case_standard | 108836 ms | 98026 ms | -10810 ms | -11.0% | 0.0% |

## Case Results

| Case | Benchmark Mode | Category | Status | Mode | Latency | Tools |
|---|---|---|---|---|---:|---:|
| latest_visit_standard | accelerated | high_frequency | success | agent | 94052 ms | 2 |
| latest_visit_standard | forced_full_agent | high_frequency | error | agent | 120016 ms | 0 |
| patient_profile_standard | accelerated | high_frequency | success | agent | 104913 ms | 2 |
| patient_profile_standard | forced_full_agent | high_frequency | success | agent | 103266 ms | 2 |
| medical_case_standard | accelerated | high_frequency | error | agent | 120034 ms | 0 |
| medical_case_standard | forced_full_agent | high_frequency | success | agent | 95727 ms | 2 |
| latest_visit_standard | accelerated | high_frequency | success | agent | 96721 ms | 2 |
| latest_visit_standard | forced_full_agent | high_frequency | success | agent | 102275 ms | 2 |
| patient_profile_standard | accelerated | high_frequency | success | agent | 82551 ms | 2 |
| patient_profile_standard | forced_full_agent | high_frequency | success | agent | 92073 ms | 2 |
| medical_case_standard | accelerated | high_frequency | success | agent | 108836 ms | 2 |
| medical_case_standard | forced_full_agent | high_frequency | success | agent | 100325 ms | 2 |
| latest_visit_standard | accelerated | high_frequency | error | agent | 120015 ms | 0 |
| latest_visit_standard | forced_full_agent | high_frequency | success | agent | 91742 ms | 2 |
| patient_profile_standard | accelerated | high_frequency | success | agent | 102494 ms | 2 |
| patient_profile_standard | forced_full_agent | high_frequency | success | agent | 83023 ms | 2 |
| medical_case_standard | accelerated | high_frequency | error | agent | 120005 ms | 0 |
| medical_case_standard | forced_full_agent | high_frequency | error | agent | 120015 ms | 0 |
