import { Fragment, ReactNode } from "react";

import type { ChatMessage } from "../../types/agent";

type MessageListProps = {
  messages: ChatMessage[];
  emptyTitle?: string;
  emptyDescription?: string;
};

type HighlightTone = "summary" | "advice" | "warning" | "risk";

function renderInline(text: string) {
  return text.replace(/\*\*(.*?)\*\*/g, "$1");
}

function normalizeTableBlock(content: string) {
  if (!content.includes("|项目|") || !content.includes(":---")) {
    return content;
  }

  const cells = content
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => item !== ":---" && item !== "---");

  const startIndex = cells.findIndex((item) => item === "检查时间" || item === "项目");
  const effectiveCells = startIndex >= 0 ? cells.slice(startIndex) : cells;

  const rows: string[] = [];
  for (let index = 0; index < effectiveCells.length; index += 3) {
    const metric = effectiveCells[index];
    const value = effectiveCells[index + 1];
    const reference = effectiveCells[index + 2];

    if (!metric || metric === "项目") {
      continue;
    }

    const parts = [`- ${metric}：${value || "未提供"}`];
    if (reference && reference !== "参考范围") {
      parts.push(`（参考：${reference}）`);
    }
    rows.push(parts.join(""));
  }

  if (rows.length === 0) {
    return content;
  }

  return ["### 关键指标", ...rows].join("\n");
}

function normalizeNumberedParagraph(content: string) {
  return content
    .replace(/([。；：])\s*(\d+\.)/g, "$1\n$2")
    .replace(/\s+(- )/g, "\n$1");
}

function normalizeAssistantContent(content: string) {
  return normalizeNumberedParagraph(normalizeTableBlock(content));
}

function getHighlightTone(text: string): { tone: HighlightTone; label: string } | null {
  const normalized = text.replace(/\*/g, "");
  if (/^(最终答案|结论|总结|摘要|本次重点)[:：]/.test(normalized)) {
    return { tone: "summary", label: "结论摘要" };
  }
  if (/^(建议|处理建议|复诊建议|用药建议|医疗建议)[:：]/.test(normalized)) {
    return { tone: "advice", label: "行动建议" };
  }
  if (/^(注意|注意事项|提醒|温馨提示|免责声明)[:：]/.test(normalized)) {
    return { tone: "warning", label: "注意事项" };
  }
  if (/^(风险|风险提醒|紧急情况|警示|异常提示与风险)[:：]/.test(normalized)) {
    return { tone: "risk", label: "风险提醒" };
  }
  return null;
}

function highlightClasses(tone: HighlightTone) {
  switch (tone) {
    case "summary":
      return "border-teal-200 bg-teal-50/80";
    case "advice":
      return "border-sky-200 bg-sky-50/80";
    case "warning":
      return "border-amber-200 bg-amber-50/80";
    case "risk":
      return "border-rose-200 bg-rose-50/80";
  }
}

function renderParagraphBlock(block: string, key: string) {
  const trimmed = block.trim();
  if (!trimmed) {
    return null;
  }

  if (/^---+$/.test(trimmed)) {
    return <hr key={key} className="border-slate-200" />;
  }

  const highlight = getHighlightTone(trimmed);
  if (highlight) {
    const [, rest = ""] = trimmed.split(/[:：]/, 2);
    return (
      <div
        key={key}
        className={`rounded-3xl border px-4 py-4 ${highlightClasses(highlight.tone)}`}
      >
        <p className="text-[11px] font-normal uppercase tracking-[0.18em] text-slate-500">
          {highlight.label}
        </p>
        <div className="mt-3 text-[14px] font-normal leading-7 text-slate-800">
          {renderInline(rest.trim() || trimmed)}
        </div>
      </div>
    );
  }

  const lines = trimmed.split("\n").map((line) => line.trim()).filter(Boolean);
  if (lines.every((line) => /^(\d+\.|[-*])\s+/.test(line))) {
    const ordered = lines.every((line) => /^\d+\.\s+/.test(line));
    const ListTag = ordered ? "ol" : "ul";
    return (
      <ListTag
        key={key}
        className={`space-y-2 pl-5 text-[14px] font-normal leading-7 text-slate-700 ${
          ordered ? "list-decimal" : "list-disc"
        }`}
      >
        {lines.map((line, index) => (
          <li key={`${key}-${index}`}>{renderInline(line.replace(/^(\d+\.|[-*])\s+/, ""))}</li>
        ))}
      </ListTag>
    );
  }

  if (/^#{1,6}\s+/.test(trimmed)) {
    const plainTitle = trimmed.replace(/^#{1,6}\s+/, "");
    return (
      <h3 key={key} className="text-[16px] font-normal text-slate-900">
        {renderInline(plainTitle)}
      </h3>
    );
  }

  if (trimmed.startsWith(">")) {
    return (
      <blockquote
        key={key}
        className="border-l-4 border-teal-200 bg-teal-50/70 px-4 py-3 text-[14px] font-normal leading-7 text-slate-700"
      >
        {renderInline(trimmed.replace(/^>\s?/, ""))}
      </blockquote>
    );
  }

  return (
    <p key={key} className="text-[14px] font-normal leading-7 text-slate-700">
      {renderInline(trimmed)}
    </p>
  );
}

function renderRichContent(content: string, isUser: boolean) {
  const normalizedContent = isUser ? content : normalizeAssistantContent(content);
  const blocks = normalizedContent
    .replace(/\r\n/g, "\n")
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, index) => renderParagraphBlock(block, `block-${index}`));
}

function renderToolSummary(message: ChatMessage): ReactNode {
  if (!message.toolOutputs || message.toolOutputs.length === 0) {
    return null;
  }

  return (
    <details className="mt-5 rounded-3xl border border-slate-200 bg-slate-50 p-4">
      <summary className="cursor-pointer text-sm font-medium text-slate-700">
        查看工具调用结果
      </summary>
      <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-700">
        {JSON.stringify(message.toolOutputs, null, 2)}
      </pre>
    </details>
  );
}

function assistantTone(toolCount: number) {
  return toolCount > 0 ? "已结合患者资料" : "文本回复";
}

export function MessageList({
  messages,
  emptyTitle = "开始新的患者会话",
  emptyDescription = "可以直接提问，也可以使用左侧快捷问题快速开始。"
}: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-[32px] border border-dashed border-slate-300 bg-white/75 p-10 text-center shadow-panel">
        <div className="max-w-md space-y-3">
          <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Conversation</p>
          <h2 className="text-2xl font-semibold text-slate-900">{emptyTitle}</h2>
          <p className="text-sm leading-7 text-slate-600">{emptyDescription}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {messages.map((message) => {
        const isUser = message.role === "user";

        return (
          <article
            key={message.id}
            className={`message-card-enter overflow-hidden rounded-[32px] border shadow-panel ${
              isUser
                ? "ml-12 border-teal-200 bg-[linear-gradient(135deg,_rgba(240,253,250,1),_rgba(255,255,255,0.98))]"
                : "mr-12 border-slate-200 bg-white"
            }`}
          >
            <div
              className={`border-b px-5 py-4 ${
                isUser
                  ? "border-teal-100 bg-[linear-gradient(135deg,_rgba(15,118,110,0.08),_rgba(255,255,255,0.85))]"
                  : "border-slate-100 bg-[linear-gradient(135deg,_rgba(226,232,240,0.45),_rgba(255,255,255,0.98))]"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                    {isUser ? "用户提问" : "助手回复"}
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[11px] text-slate-600 ring-1 ring-slate-200">
                    {isUser ? "当前会话" : assistantTone(message.toolOutputs?.length ?? 0)}
                  </span>
                </div>
                {message.status === "pending" ? (
                  <span className="text-xs text-amber-600">处理中</span>
                ) : null}
              </div>
            </div>

            <div className="p-5">
              <div className={`space-y-4 ${isUser ? "text-[15px]" : "message-prose"}`}>
                {renderRichContent(message.content, isUser)}
              </div>

              {message.imageUrl ? (
                <img
                  src={message.imageUrl}
                  alt="用户上传图片"
                  className="mt-5 max-h-72 rounded-3xl border border-slate-200 object-cover"
                />
              ) : null}

              {renderToolSummary(message)}
            </div>
          </article>
        );
      })}
    </div>
  );
}
