import { create } from "zustand";

import type { ChatMessage } from "../types/agent";

type WorkspaceState = {
  patientCode: string;
  draft: string;
  selectedImage: File | null;
  messages: ChatMessage[];
  conversations: Record<string, ChatMessage[]>;
  setPatientCode: (value: string) => void;
  setDraft: (value: string) => void;
  setSelectedImage: (file: File | null) => void;
  addMessage: (message: ChatMessage) => void;
  replaceMessages: (messages: ChatMessage[]) => void;
  clearMessages: () => void;
};

function normalizePatientCode(value: string) {
  return value.trim().toUpperCase();
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  patientCode: "P0003",
  draft: "",
  selectedImage: null,
  messages: [],
  conversations: {},
  setPatientCode: (value) =>
    set((state) => {
      const patientCode = normalizePatientCode(value);
      return {
        patientCode,
        messages: state.conversations[patientCode] ?? []
      };
    }),
  setDraft: (value) => set({ draft: value }),
  setSelectedImage: (file) => set({ selectedImage: file }),
  addMessage: (message) =>
    set((state) => {
      const currentMessages = [...(state.conversations[state.patientCode] ?? []), message];
      return {
        messages: currentMessages,
        conversations: {
          ...state.conversations,
          [state.patientCode]: currentMessages
        }
      };
    }),
  replaceMessages: (messages) =>
    set((state) => ({
      messages,
      conversations: {
        ...state.conversations,
        [state.patientCode]: messages
      }
    })),
  clearMessages: () =>
    set((state) => ({
      messages: [],
      conversations: {
        ...state.conversations,
        [state.patientCode]: []
      }
    }))
}));
