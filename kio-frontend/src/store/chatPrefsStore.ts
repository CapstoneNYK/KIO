import { create } from "zustand";

export type ChatScale = 1 | 1.25 | 1.5;
export const CHAT_SCALES: { value: ChatScale; label: string }[] = [
  { value: 1, label: "보통" },
  { value: 1.25, label: "크게" },
  { value: 1.5, label: "아주 크게" },
];

const KEY = "kio.chatPrefs";

function load(): { scale: ChatScale; ttsOn: boolean } {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw);
      const scale = [1, 1.25, 1.5].includes(p.scale) ? (p.scale as ChatScale) : 1.25;
      return { scale, ttsOn: p.ttsOn !== false };
    }
  } catch {
  }
  return { scale: 1.25, ttsOn: true };
}

function save(scale: ChatScale, ttsOn: boolean) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ scale, ttsOn }));
  } catch {
  }
}

interface ChatPrefs {
  scale: ChatScale;
  ttsOn: boolean;
  setScale: (s: ChatScale) => void;
  setTtsOn: (v: boolean) => void;
  resetCount: number;
  resetChat: () => void;
  closeCount: number;
  closeChat: () => void;
}

export const useChatPrefs = create<ChatPrefs>((set, get) => ({
  ...load(),
  resetCount: 0,
  resetChat: () => set((s) => ({ resetCount: s.resetCount + 1 })),
  closeCount: 0,
  closeChat: () => set((s) => ({ closeCount: s.closeCount + 1 })),
  setScale: (scale) => {
    set({ scale });
    save(scale, get().ttsOn);
  },
  setTtsOn: (ttsOn) => {
    set({ ttsOn });
    save(get().scale, ttsOn);
  },
}));
