# PatientCare-Agent Benchmark Report

- Generated at: `2026-04-24T22:14:51`
- Case set: `high_frequency`
- Compare modes: `True`
- Cases: `6`
- Success rate: `83.3%`
- High-frequency acceleration hit rate: `60.0%`
- Average latency: `33643 ms`
- P50 latency: `79 ms`
- P95 latency: `97966 ms`
- Accelerated average latency: `69 ms`
- Non-accelerated average latency: `84004 ms`
- Acceleration latency delta: `83935 ms`

## Mode Comparison

- Accelerated runs: `3`
- Forced full-agent runs: `2`
- Accelerated average latency: `69 ms`
- Forced full-agent average latency: `84004 ms`
- Accelerated P95 latency: `79 ms`
- Forced full-agent P95 latency: `97966 ms`
- Latency delta: `83935 ms`
- Latency reduction: `99.9%`
- Accelerated hit rate: `100.0%`

## By Category

| Category | Cases | Avg Latency | P95 Latency | Acceleration Hit Rate |
|---|---:|---:|---:|---:|
| high_frequency | 5 | 33643 ms | 97966 ms | 60.0% |

## By Benchmark Mode

| Mode | Cases | Avg Latency | P95 Latency | Acceleration Hit Rate |
|---|---:|---:|---:|---:|
| accelerated | 3 | 69 ms | 79 ms | 100.0% |
| forced_full_agent | 2 | 84004 ms | 97966 ms | 0.0% |

## Per Case Comparison

| Case | Accelerated Avg | Forced Full-Agent Avg | Delta | Reduction | Hit Rate |
|---|---:|---:|---:|---:|---:|
| patient_profile_standard | 59 ms | 97966 ms | 97907 ms | 99.9% | 100.0% |
| medical_case_standard | 68 ms | 70043 ms | 69975 ms | 99.9% | 100.0% |

## Case Results

| Case | Benchmark Mode | Category | Status | Mode | Latency | Tools |
|---|---|---|---|---|---:|---:|
| latest_visit_standard | accelerated | high_frequency | success | high_frequency_acceleration | 79 ms | 2 |
| latest_visit_standard | forced_full_agent | high_frequency | error | agent | 120026 ms | 0 |
| patient_profile_standard | accelerated | high_frequency | success | high_frequency_acceleration | 59 ms | 2 |
| patient_profile_standard | forced_full_agent | high_frequency | success | agent | 97966 ms | 2 |
| medical_case_standard | accelerated | high_frequency | success | high_frequency_acceleration | 68 ms | 2 |
| medical_case_standard | forced_full_agent | high_frequency | success | agent | 70043 ms | 2 |
