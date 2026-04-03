export type AgentImageInput = {
  image_base64: string;
  mime_type: string;
};

export type AgentQueryRequest = {
  query: string;
  images: AgentImageInput[];
  debug_planner: boolean;
};

export type AgentToolOutput = {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
};

export type AgentQueryResponse = {
  answer: string;
  tool_outputs: AgentToolOutput[];
  planner_debug?: Record<string, unknown> | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  imageUrl?: string;
  toolOutputs?: AgentToolOutput[];
  status?: "pending" | "error" | "done";
};

