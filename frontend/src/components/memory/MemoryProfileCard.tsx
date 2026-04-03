import type { MemoryPreference, UserProfile } from "../../types/dashboard";

type MemoryProfileCardProps = {
  profile?: UserProfile | null;
  preference?: MemoryPreference | null;
  isLoading?: boolean;
  errorMessage?: string | null;
};

function InfoBlock({
  label,
  value
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div className="rounded-3xl bg-slate-50 px-4 py-4">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-3 text-sm leading-7 text-slate-700">{value || "暂无相关信息。"}</p>
    </div>
  );
}

export function MemoryProfileCard({
  profile,
  preference,
  isLoading = false,
  errorMessage
}: MemoryProfileCardProps) {
  return (
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(14,165,233,0.08),_rgba(255,255,255,0.96))] px-5 py-4">
        <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Memory Profile</p>
        <h3 className="mt-2 text-lg font-semibold text-slate-950">长期记忆摘要</h3>
      </div>

      <div className="p-5">
        {isLoading ? (
          <div className="space-y-3">
            <div className="h-20 rounded-3xl bg-slate-100" />
            <div className="h-20 rounded-3xl bg-slate-100" />
            <div className="h-20 rounded-3xl bg-slate-100" />
          </div>
        ) : errorMessage ? (
          <div className="rounded-3xl border border-rose-100 bg-rose-50 px-4 py-4 text-sm leading-7 text-rose-700">
            {errorMessage}
          </div>
        ) : (
          <div className="space-y-3">
            <InfoBlock label="用户画像" value={profile?.profile_summary} />
            <InfoBlock
              label="稳定偏好"
              value={profile?.stable_preferences || preference?.additional_preferences}
            />
            <InfoBlock
              label="关注主题"
              value={profile?.preferred_topics || preference?.focus_topics}
            />
          </div>
        )}
      </div>
    </section>
  );
}
