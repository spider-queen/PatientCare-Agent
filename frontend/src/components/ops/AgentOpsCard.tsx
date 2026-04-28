import type { AgentOpsOverviewResponse } from "../../types/dashboard";

type AgentOpsCardProps = {
  data?: AgentOpsOverviewResponse;
  isLoading: boolean;
  errorMessage?: string | null;
};

function formatDuration(value?: number) {
  if (!value) {
    return "0 ms";
  }
  return `${value} ms`;
}

function formatRate(value?: number) {
  if (!value) {
    return "0%";
  }
  return `${value.toFixed(1)}%`;
}

export function AgentOpsCard({ data, isLoading, errorMessage }: AgentOpsCardProps) {
  const summary = data?.summary;
  const recentRuns = data?.recent_runs ?? [];

  const metricItems = [
    { label: "P50 响应耗时", value: formatDuration(summary?.p50_total_duration_ms) },
    { label: "P95 响应耗时", value: formatDuration(summary?.p95_total_duration_ms) },
    {
      label: "自适应路由命中率",
      value: formatRate(summary?.adaptive_route_hit_rate)
    },
    { label: "语义缓存命中率", value: formatRate(summary?.semantic_cache_hit_rate) },
    { label: "工具调用成功率", value: formatRate(summary?.tool_success_rate) },
    { label: "风险拦截次数", value: String(summary?.risk_guard_block_count ?? 0) }
  ];

  return (
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(14,165,233,0.08),_rgba(255,255,255,0.96))] px-5 py-4">
        <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Agent Ops</p>
        <div className="mt-2 flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-slate-950">运行看板</h3>
          <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
            {summary ? `最近 ${summary.window_size} 次` : "暂无数据"}
          </span>
        </div>
      </div>

      <div className="space-y-4 px-5 py-5">
        {isLoading ? (
          <p className="text-sm text-slate-500">正在加载 Agent 运行指标...</p>
        ) : errorMessage ? (
          <p className="text-sm text-rose-500">{errorMessage}</p>
        ) : !summary ? (
          <p className="text-sm text-slate-500">
            暂无 Agent 运行记录。发送几次请求后会生成看板快照。
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              {metricItems.map((item) => (
                <div
                  key={item.label}
                  className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3"
                >
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    {item.label}
                  </p>
                  <p className="mt-2 text-xl font-semibold text-slate-950">{item.value}</p>
                </div>
              ))}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                运行比例
              </p>
              <div className="mt-3 grid gap-2 text-sm text-slate-700">
                <div className="flex items-center justify-between">
                  <span>证据缓存失效率</span>
                  <span>{formatRate(summary.evidence_cache_invalid_rate)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>完整 Agent Loop fallback</span>
                  <span>{formatRate(summary.agent_loop_fallback_rate)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>平均延迟节省</span>
                  <span>{formatDuration(summary.avg_latency_saved_ms)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>意图低置信度比例</span>
                  <span>{formatRate(summary.low_confidence_intent_rate)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>记忆回退率</span>
                  <span>{formatRate(summary.memory_fallback_rate)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>工具直达 / Agent 平均耗时</span>
                  <span>
                    {formatDuration(summary.fast_path_avg_duration_ms)} /{" "}
                    {formatDuration(summary.full_agent_avg_duration_ms)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>平均工具数</span>
                  <span>{summary.avg_tool_count}</span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  最近运行记录
                </p>
                <span className="text-xs text-slate-500">
                  平均执行 {formatDuration(summary.stage_breakdown_avg_ms.agent_execution_ms)}
                </span>
              </div>
              <div className="mt-3 space-y-3">
                {recentRuns.slice(0, 3).map((run) => (
                  <div
                    key={run.run_id}
                    className="rounded-2xl border border-white/80 bg-white px-3 py-3 shadow-sm"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-slate-900">{run.intent}</span>
                      <span className="text-xs text-slate-500">
                        {formatDuration(run.total_duration_ms)}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span className="rounded-full bg-slate-100 px-2 py-1">
                        {run.route_type ?? run.execution_mode}
                      </span>
                      {run.cache_hit ? (
                        <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">
                          缓存命中
                        </span>
                      ) : null}
                      <span className="rounded-full bg-slate-100 px-2 py-1">
                        工具 {run.tool_count}
                      </span>
                      {run.tool_blocked_count ? (
                        <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">
                          拦截 {run.tool_blocked_count}
                        </span>
                      ) : null}
                      {run.risk_level ? (
                        <span className="rounded-full bg-rose-50 px-2 py-1 text-rose-700">
                          风险 {run.risk_level}
                        </span>
                      ) : null}
                      <span className="rounded-full bg-slate-100 px-2 py-1">
                        {run.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
