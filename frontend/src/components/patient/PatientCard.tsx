import type { Patient } from "../../types/dashboard";

type PatientCardProps = {
  patient?: Patient | null;
  isLoading?: boolean;
  errorMessage?: string | null;
};

function FieldBlock({
  label,
  value
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div className="rounded-3xl bg-slate-50 px-4 py-4">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-3 text-sm leading-7 text-slate-700">{value || "暂无信息"}</p>
    </div>
  );
}

function maskPhone(value?: string | null) {
  if (!value || value.length < 7) {
    return value;
  }
  return `${value.slice(0, 3)}****${value.slice(-4)}`;
}

function maskIdNumber(value?: string | null) {
  if (!value || value.length < 8) {
    return value;
  }
  return `${value.slice(0, 4)}********${value.slice(-4)}`;
}

export function PatientCard({ patient, isLoading = false, errorMessage }: PatientCardProps) {
  if (isLoading) {
    return (
      <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
        <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.1),_rgba(255,255,255,0.95))] px-5 py-4">
          <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Patient Overview</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-950">患者概览</h3>
        </div>
        <div className="space-y-3 p-5">
          <div className="h-6 w-32 rounded-full bg-slate-200" />
          <div className="h-4 w-24 rounded-full bg-slate-200" />
          <div className="h-20 rounded-3xl bg-slate-100" />
          <div className="h-20 rounded-3xl bg-slate-100" />
        </div>
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="overflow-hidden rounded-[28px] border border-rose-200 bg-white shadow-panel">
        <div className="border-b border-rose-100 bg-[linear-gradient(135deg,_rgba(251,113,133,0.12),_rgba(255,255,255,0.96))] px-5 py-4">
          <p className="text-[11px] uppercase tracking-[0.26em] text-rose-600">Patient Overview</p>
          <h3 className="mt-2 text-lg font-semibold text-rose-900">患者概览加载失败</h3>
        </div>
        <div className="p-5 text-sm leading-7 text-rose-700">{errorMessage}</div>
      </section>
    );
  }

  if (!patient) {
    return (
      <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
        <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.1),_rgba(255,255,255,0.95))] px-5 py-4">
          <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Patient Overview</p>
          <h3 className="mt-2 text-lg font-semibold text-slate-950">患者概览</h3>
        </div>
        <div className="p-5 text-sm leading-7 text-slate-500">当前编号尚未匹配到患者信息。</div>
      </section>
    );
  }

  return (
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.1),_rgba(255,255,255,0.95))] px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Patient Overview</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">患者概览</h3>
          </div>
          <span className="rounded-full bg-accentSoft px-3 py-1 text-xs font-medium text-accent">
            已关联
          </span>
        </div>
      </div>

      <div className="p-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">{patient.full_name}</h2>
          <p className="mt-1 text-sm text-slate-500">{patient.patient_code}</p>
        </div>

        <div className="mt-5 grid gap-3">
          <FieldBlock label="联系方式" value={maskPhone(patient.phone)} />
          <FieldBlock label="身份证号" value={maskIdNumber(patient.id_number)} />
          <FieldBlock label="出生日期" value={patient.date_of_birth} />
          <FieldBlock label="地址" value={patient.address} />
        </div>
      </div>
    </section>
  );
}
