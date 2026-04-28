import { ChangeEvent, FormEvent } from "react";

type MessageInputProps = {
  draft: string;
  patientCode: string;
  selectedImage: File | null;
  isSubmitting: boolean;
  helperText?: string;
  onDraftChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
  onSubmit: () => void;
};

export function MessageInput({
  draft,
  patientCode,
  selectedImage,
  isSubmitting,
  helperText,
  onDraftChange,
  onFileChange,
  onSubmit
}: MessageInputProps) {
  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    onFileChange(file);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-panel"
    >
      <div className="border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.1),_rgba(255,255,255,0.96))] px-5 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Clinician Input</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">问答输入区</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
              当前患者：{patientCode || "未选择"}
            </span>
            <span className="rounded-full bg-accentSoft px-3 py-1 text-xs font-medium text-accent">
              单图输入
            </span>
          </div>
        </div>
      </div>

      <div className="p-5">
        <textarea
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          rows={6}
          placeholder="输入问题，例如：请总结最近一次复诊重点，或结合图片解释检查结果。"
          className="min-h-[220px] w-full resize-none rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,_#f8fbff,_#f8fafc)] px-5 py-4 text-base leading-8 text-slate-900 outline-none transition duration-200 focus:border-accent focus:bg-white focus:shadow-[0_0_0_4px_rgba(13,148,136,0.08)]"
        />

        <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <label className="flex cursor-pointer items-center gap-3 text-sm text-slate-600">
              <span className="rounded-full border border-slate-300 bg-white px-4 py-2 transition hover:border-accent hover:text-accent">
                {selectedImage ? "更换图片" : "上传图片"}
              </span>
              <input type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
              <span className="truncate">{selectedImage ? selectedImage.name : "未选择图片"}</span>
            </label>
            <p className="text-xs leading-6 text-slate-500">
              适合上传检查单、化验单或图像资料，并结合文本一起提问。
            </p>
          </div>

          <div className="flex min-w-[260px] flex-col items-start gap-3 lg:items-end">
            {helperText ? <p className="text-xs leading-6 text-amber-700">{helperText}</p> : null}
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-ink px-7 py-3 text-sm font-semibold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400 disabled:hover:translate-y-0"
            >
              {isSubmitting ? "等待助手回复" : "发送提问"}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
