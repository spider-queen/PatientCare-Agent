import { FormEvent } from "react";

type PatientLookupCardProps = {
  patientCode: string;
  prompts: string[];
  onPatientCodeChange: (value: string) => void;
  onPromptSelect: (value: string) => void;
};

export function PatientLookupCard({
  patientCode,
  prompts,
  onPatientCodeChange,
  onPromptSelect
}: PatientLookupCardProps) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
  };

  return (
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.1),_rgba(255,255,255,0.95))] px-5 py-4">
        <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Clinical Copilot</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          医疗智能随访平台
        </h1>
      </div>

      <div className="p-5">
        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block text-sm font-medium text-slate-700">患者编号</label>
          <input
            value={patientCode}
            onChange={(event) => onPatientCodeChange(event.target.value)}
            placeholder="例如 P0003"
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm uppercase text-slate-900 outline-none transition focus:border-accent focus:bg-white"
          />
          <p className="text-xs leading-6 text-slate-500">
            切换患者后，会自动切换到该患者对应的会话和快捷问题。
          </p>
        </form>

        <div className="mt-6 space-y-3">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">快捷问题</p>
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onPromptSelect(prompt)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm leading-6 text-slate-700 transition hover:border-accent hover:bg-white"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
