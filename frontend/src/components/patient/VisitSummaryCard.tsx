import type { VisitRecord } from "../../types/dashboard";

type VisitSummaryCardProps = {
  visit?: VisitRecord | null;
  isLoading?: boolean;
  errorMessage?: string | null;
};

function formatVisitDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN");
}

export function VisitSummaryCard({
  visit,
  isLoading = false,
  errorMessage
}: VisitSummaryCardProps) {
  return (
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.1),_rgba(255,255,255,0.95))] px-5 py-4">
        <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Recent Visit</p>
        <h3 className="mt-2 text-lg font-semibold text-slate-950">最近一次就诊</h3>
      </div>

      <div className="p-5">
        {isLoading ? (
          <div className="space-y-3">
            <div className="h-5 w-40 rounded-full bg-slate-200" />
            <div className="h-24 rounded-3xl bg-slate-100" />
            <div className="h-16 rounded-3xl bg-slate-100" />
          </div>
        ) : errorMessage ? (
          <div className="rounded-3xl border border-rose-100 bg-rose-50 px-4 py-4 text-sm leading-7 text-rose-700">
            {errorMessage}
          </div>
        ) : visit ? (
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xl font-semibold text-slate-950">
                  {visit.department || "未标注科室"}
                </p>
                <p className="mt-1 text-sm text-slate-500">{visit.visit_type || "门诊记录"}</p>
              </div>
              <span className="rounded-full bg-peach px-3 py-1 text-xs font-medium text-orange-700">
                {formatVisitDate(visit.visit_time)}
              </span>
            </div>

            <div className="rounded-3xl bg-slate-50 px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">本次摘要</p>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                {visit.summary || visit.notes || "暂无摘要内容。"}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-3xl border border-slate-200 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">接诊医生</p>
                <p className="mt-2 text-sm font-medium text-slate-800">
                  {visit.physician_name || "未记录"}
                </p>
              </div>
              <div className="rounded-3xl border border-slate-200 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">就诊编号</p>
                <p className="mt-2 text-sm font-medium text-slate-800">
                  {visit.visit_code || "未记录"}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm leading-7 text-slate-500">
            当前患者暂无就诊记录。
          </div>
        )}
      </div>
    </section>
  );
}
