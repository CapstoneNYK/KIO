import { create } from "zustand";

// 어르신이 읽기 편하도록 채팅창 글자 크기와 음성 안내(TTS) 사용 여부를 고를 수 있게 한다.
// 값은 브라우저에 저장해 다음에도 유지한다 (저장소를 못 쓰는 환경에서는 기본값으로 동작).
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
    /* 저장소를 쓸 수 없으면 기본값 */
  }
  // 기본값: 어르신 대상이므로 '크게' + 음성 안내 켬
  return { scale: 1.25, ttsOn: true };
}

function save(scale: ChatScale, ttsOn: boolean) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ scale, ttsOn }));
  } catch {
    /* 무시 */
  }
}

interface ChatPrefs {
  scale: ChatScale;
  ttsOn: boolean;
  setScale: (s: ChatScale) => void;
  setTtsOn: (v: boolean) => void;
  /** 주문이 끝나면 올려서 채팅 내역을 비운다 */
  resetCount: number;
  resetChat: () => void;
}

export const useChatPrefs = create<ChatPrefs>((set, get) => ({
  ...load(),
  resetCount: 0,
  resetChat: () => set((s) => ({ resetCount: s.resetCount + 1 })),
  setScale: (scale) => {
    set({ scale });
    save(scale, get().ttsOn);
  },
  setTtsOn: (ttsOn) => {
    set({ ttsOn });
    save(get().scale, ttsOn);
  },
}));
