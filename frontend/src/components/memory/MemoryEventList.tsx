import type { MemoryEvent } from "../../types/dashboard";

type MemoryEventListProps = {
  events: MemoryEvent[];
  isLoading?: boolean;
  errorMessage?: string | null;
};

function formatEventDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN");
}

export function MemoryEventList({
  events,
  isLoading = false,
  errorMessage
}: MemoryEventListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="h-24 rounded-3xl bg-slate-100" />
        <div className="h-24 rounded-3xl bg-slate-100" />
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="rounded-3xl border border-rose-100 bg-rose-50 px-4 py-4 text-sm leading-7 text-rose-700">
        {errorMessage}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm leading-7 text-slate-500">
        当前患者暂无关键事件记录。
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <article
          key={event.id}
          className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">{event.title}</h4>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                {event.event_type}
              </p>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-500 ring-1 ring-slate-200">
              {formatEventDate(event.event_time)}
            </span>
          </div>
          <p className="mt-3 text-sm leading-7 text-slate-700">
            {event.summary || "暂无事件摘要。"}
          </p>
        </article>
      ))}
    </div>
  );
}
