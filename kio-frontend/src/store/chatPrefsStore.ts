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
  openCount: number;
  openChat: () => void;
  // 옵션 되묻기 대화가 진행 중인지 (창이 자동으로 닫혀도 이어서 열어야 하는지 판단)
  dialogActive: boolean;
  setDialogActive: (v: boolean) => void;
  // 화면에서 직접 담거나 주문하기를 눌렀을 때, 진행 중이던 음성 되묻기를 멈추는 신호
  dialogCancelCount: number;
  cancelDialog: () => void;
}

export const useChatPrefs = create<ChatPrefs>((set, get) => ({
  ...load(),
  resetCount: 0,
  resetChat: () => set((s) => ({ resetCount: s.resetCount + 1 })),
  closeCount: 0,
  closeChat: () => set((s) => ({ closeCount: s.closeCount + 1 })),
  openCount: 0,
  openChat: () => set((s) => ({ openCount: s.openCount + 1 })),
  dialogActive: false,
  setDialogActive: (dialogActive) => set({ dialogActive }),
  dialogCancelCount: 0,
  cancelDialog: () =>
    set((s) => (s.dialogActive ? { dialogActive: false, dialogCancelCount: s.dialogCancelCount + 1 } : s)),
  setScale: (scale) => {
    set({ scale });
    save(scale, get().ttsOn);
  },
  setTtsOn: (ttsOn) => {
    set({ ttsOn });
    save(get().scale, ttsOn);
  },
}));
