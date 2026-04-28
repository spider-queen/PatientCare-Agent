import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { useWorkspaceStore } from "../../app/store";
import { MessageInput } from "../../components/chat/MessageInput";
import { MessageList } from "../../components/chat/MessageList";
import { WorkspaceShell } from "../../components/layout/WorkspaceShell";
import { MemoryEventList } from "../../components/memory/MemoryEventList";
import { MemoryProfileCard } from "../../components/memory/MemoryProfileCard";
import { AgentOpsCard } from "../../components/ops/AgentOpsCard";
import { PatientCard } from "../../components/patient/PatientCard";
import { PatientLookupCard } from "../../components/patient/PatientLookupCard";
import { VisitSummaryCard } from "../../components/patient/VisitSummaryCard";
import { useAgentOpsOverview } from "../../hooks/useAgentOpsOverview";
import { usePatientOverview } from "../../hooks/usePatientOverview";
import { queryAgent } from "../../services/agent";
import type { AgentQueryRequest, ChatMessage } from "../../types/agent";
import type { Patient } from "../../types/dashboard";

type SubmitSnapshot = {
  rawDraft: string;
  prompt: string;
  imageFile: File | null;
  previewUrl?: string;
};

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const [, base64 = ""] = result.split(",");
      resolve(base64);
    };
    reader.onerror = () => reject(new Error("图片读取失败"));
    reader.readAsDataURL(file);
  });
}

function buildQuickPrompts(patient?: Patient | null) {
  const subject = patient?.full_name || "该患者";
  return [
    `请总结${subject}最近一次心内科复诊重点。`,
    `请帮我梳理${subject}最近的用药提醒。`,
    `请查看${subject}接下来的随访计划。`
  ];
}

export function WorkspacePage() {
  const {
    patientCode,
    draft,
    selectedImage,
    messages,
    setPatientCode,
    setDraft,
    setSelectedImage,
    addMessage
  } = useWorkspaceStore();
  const previousPatientCodeRef = useRef<string | null>(null);
  const [isEventPanelOpen, setIsEventPanelOpen] = useState(false);
  const overviewQuery = usePatientOverview(patientCode);
  const opsQuery = useAgentOpsOverview();
  const activePatient = overviewQuery.data?.patient;
  const quickPrompts = useMemo(() => buildQuickPrompts(activePatient), [activePatient]);

  useEffect(() => {
    const isInitialLoad = previousPatientCodeRef.current === null;
    const patientChanged = previousPatientCodeRef.current !== patientCode;
    previousPatientCodeRef.current = patientCode;

    if (isInitialLoad || patientChanged) {
      setDraft("");
      setSelectedImage(null);
    }
  }, [patientCode, setDraft, setSelectedImage]);

  const queryMutation = useMutation({
    mutationFn: async (snapshot: SubmitSnapshot) => {
      const payload: AgentQueryRequest = {
        query: snapshot.prompt,
        patient_code: patientCode || null,
        images: [],
        debug_planner: false
      };

      if (snapshot.imageFile) {
        payload.images.push({
          image_base64: await fileToBase64(snapshot.imageFile),
          mime_type: snapshot.imageFile.type || "image/png"
        });
      }

      return queryAgent(payload);
    },
    onMutate: async (snapshot) => {
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: snapshot.rawDraft,
        imageUrl: snapshot.previewUrl,
        status: "done"
      };
      addMessage(userMessage);
      setDraft("");
      setSelectedImage(null);
    },
    onSuccess: (data) => {
      addMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.answer,
        toolOutputs: data.tool_outputs,
        intent: data.intent,
        intentConfidence: data.intent_confidence,
        routeType: data.route_type,
        routeReason: data.route_reason,
        cacheHit: data.cache_hit,
        evidence: data.evidence,
        riskLevel: data.risk_level,
        recommendedAction: data.recommended_action,
        status: "done"
      });
      void overviewQuery.refetch();
      void opsQuery.refetch();
    },
    onError: (error) => {
      addMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        content: error instanceof Error ? error.message : "请求失败，请稍后重试。",
        status: "error"
      });
    }
  });

  const errorMessage =
    overviewQuery.error instanceof Error ? overviewQuery.error.message : null;

  return (
    <WorkspaceShell
      left={
        <>
          <PatientLookupCard
            patientCode={patientCode}
            prompts={quickPrompts}
            onPatientCodeChange={setPatientCode}
            onPromptSelect={(prompt) => {
              setDraft(prompt);
            }}
          />
          <PatientCard
            patient={overviewQuery.data?.patient}
            isLoading={overviewQuery.isLoading}
            errorMessage={errorMessage}
          />
        </>
      }
      right={
        <>
          <VisitSummaryCard
            visit={overviewQuery.data?.latest_visit}
            isLoading={overviewQuery.isLoading}
            errorMessage={errorMessage ? "最近一次就诊加载失败。" : null}
          />
          <MemoryProfileCard
            profile={overviewQuery.data?.user_profile}
            preference={overviewQuery.data?.memory_preference}
            isLoading={overviewQuery.isLoading}
            errorMessage={errorMessage ? "长期记忆摘要加载失败。" : null}
          />
          <AgentOpsCard
            data={opsQuery.data}
            isLoading={opsQuery.isLoading}
            errorMessage={opsQuery.error instanceof Error ? opsQuery.error.message : null}
          />
        </>
      }
    >
      <div className="flex h-full flex-col gap-4">
        <section className="rounded-[28px] border border-slate-200 bg-white/90 p-5 shadow-panel backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Medical AI Workspace</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                医护端诊后随访 Agent 工作台
              </h2>
            </div>
            <div className="rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white">
              {overviewQuery.isLoading
                ? "正在加载患者信息..."
                : errorMessage
                  ? `患者加载失败：${errorMessage}`
                  : `当前患者：${activePatient?.full_name || patientCode || "未选择"}`}
            </div>
          </div>
        </section>

        <section className="grid min-h-[420px] gap-4 lg:grid-rows-[minmax(0,1fr)_auto]">
          <div className="min-h-[360px] overflow-y-auto rounded-[28px]">
            <MessageList
              messages={messages}
              emptyTitle={
                activePatient?.full_name
                  ? `${activePatient.full_name} 的随访会话`
                  : "开始新的随访会话"
              }
              emptyDescription={
                errorMessage
                  ? "患者概览加载失败时，聊天仍可继续，但自动补充的患者上下文会减少。"
                  : "可以直接提问，或使用左侧快捷问题开始本患者的独立会话。"
              }
            />
          </div>
          <MessageInput
            draft={draft}
            patientCode={patientCode}
            selectedImage={selectedImage}
            isSubmitting={queryMutation.isPending}
            helperText={
              !patientCode
                ? "请先输入患者编号。"
                : errorMessage
                  ? "当前患者概览加载失败，建议先确认患者编号后再提问。"
                  : !draft.trim()
                    ? "可以直接输入问题，也可以点击左侧快捷问题开始。"
                    : undefined
            }
            onDraftChange={setDraft}
            onFileChange={setSelectedImage}
            onSubmit={() => {
              const rawDraft = draft.trim();
              const prompt = rawDraft;
              if (!prompt) {
                return;
              }

              queryMutation.mutate({
                rawDraft,
                prompt,
                imageFile: selectedImage,
                previewUrl: selectedImage ? URL.createObjectURL(selectedImage) : undefined
              });
            }}
          />

          <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-panel">
            <button
              type="button"
              onClick={() => setIsEventPanelOpen((value) => !value)}
              className="flex w-full items-center justify-between border-b border-slate-100 bg-[linear-gradient(135deg,_rgba(251,146,60,0.09),_rgba(255,255,255,0.96))] px-5 py-4 text-left"
            >
              <div>
                <p className="text-[11px] uppercase tracking-[0.26em] text-slate-500">Key Events</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-950">关键事件时间线</h3>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                {isEventPanelOpen ? "收起" : "展开"}
              </span>
            </button>

            {isEventPanelOpen ? (
              <div className="p-5">
                <MemoryEventList
                  events={overviewQuery.data?.recent_memory_events ?? []}
                  isLoading={overviewQuery.isLoading}
                  errorMessage={errorMessage ? "关键事件列表加载失败。" : null}
                />
              </div>
            ) : (
              <div className="px-5 py-4 text-sm leading-7 text-slate-500">
                默认收起关键事件，避免页面过长。需要时可展开查看完整时间线。
              </div>
            )}
          </section>
        </section>
      </div>
    </WorkspaceShell>
  );
}
