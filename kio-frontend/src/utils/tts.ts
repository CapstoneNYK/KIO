export const ttsSupported = typeof window !== "undefined" && "speechSynthesis" in window;

let koVoice: SpeechSynthesisVoice | null = null;
function pickVoice() {
  if (!ttsSupported) return;
  const voices = window.speechSynthesis.getVoices();
  koVoice =
    voices.find((v) => v.lang === "ko-KR" && /Google|Heami|SunHi|Sun-Hi|Yuna|Natural/i.test(v.name)) ??
    voices.find((v) => v.lang.toLowerCase().startsWith("ko")) ??
    null;
}
if (ttsSupported) {
  pickVoice();
  window.speechSynthesis.onvoiceschanged = pickVoice;
}

const SINO = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"];
const NATIVE = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"];
function sino(n: number): string {
  if (n >= 100) return String(n);
  if (n < 10) return SINO[n];
  const tens = Math.floor(n / 10);
  return (tens === 1 ? "" : SINO[tens]) + "십" + SINO[n % 10];
}
function toSpoken(text: string): string {
  return text
    .replace(/(\d+)\s*번/g, (_, d) => `${sino(Number(d))} 번`)
    .replace(/(\d+)\s*(잔|개|병|줄)/g, (m, d, unit) => {
      const n = Number(d);
      return n >= 1 && n <= 10 ? `${NATIVE[n]} ${unit}` : m;
    });
}

let generation = 0;
let audio: HTMLAudioElement | null = null;
let abort: AbortController | null = null;
let serverRetryAt = 0;
const audioCache = new Map<string, string>();

export function stopSpeaking() {
  generation++;
  abort?.abort();
  abort = null;
  if (audio) {
    audio.pause();
    audio = null;
  }
  if (ttsSupported) window.speechSynthesis.cancel();
}

function speakWithBrowser(text: string, mine: number, onDone?: () => void, onStart?: () => void) {
  if (!ttsSupported) {
    onDone?.();
    return;
  }
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ko-KR";
  u.rate = 1.0;
  if (koVoice) u.voice = koVoice;
  const done = () => {
    if (mine === generation) onDone?.();
  };
  u.onstart = () => {
    if (mine === generation) onStart?.();
  };
  u.onend = done;
  u.onerror = done;
  window.speechSynthesis.speak(u);
}

async function fetchServerAudio(text: string, signal: AbortSignal): Promise<string | null> {
  const cached = audioCache.get(text);
  if (cached) return cached;
  if (signal.aborted) return null;
  // 8초 제한은 이 요청만 끊는다(전역 abort 를 쓰면 그 사이 시작된 새 요청까지 끊긴다)
  const local = new AbortController();
  const onAbort = () => local.abort();
  signal.addEventListener("abort", onAbort);
  const timeout = setTimeout(() => local.abort(), 8000);
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: local.signal,
    });
    if (!res.ok) return null;
    const url = URL.createObjectURL(await res.blob());
    if (audioCache.size < 50) audioCache.set(text, url);
    return url;
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener("abort", onAbort);
  }
}

// onStart: 목소리가 실제로 나오기 시작하는 순간(음성 파일을 받아오는 시간은 빼고 센다)
export async function speak(rawText: string, onDone?: () => void, onStart?: () => void) {
  const text = toSpoken(rawText);
  if (!text.trim()) {
    onDone?.();
    return;
  }
  stopSpeaking();
  const mine = generation;

  if (Date.now() >= serverRetryAt) {
    abort = new AbortController();
    const url = await fetchServerAudio(text, abort.signal);
    if (mine !== generation) return;
    if (url) {
      const a = new Audio(url);
      audio = a;
      a.onended = () => {
        if (mine === generation) onDone?.();
      };
      a.onerror = () => {
        if (mine === generation) speakWithBrowser(text, mine, onDone, onStart);
      };
      try {
        await a.play();
        if (mine === generation) onStart?.();
        return;
      } catch {
        // 자동 재생이 막히면 아래 브라우저 음성으로 대신 읽는다
      }
    } else {
      serverRetryAt = Date.now() + 60_000;
    }
    if (mine !== generation) return;
  }
  speakWithBrowser(text, mine, onDone, onStart);
}

const MAX_SPEECH_CHARS = 110;

function copula(word: string): string {
  const code = word.trim().charCodeAt(word.trim().length - 1);
  const isHangul = code >= 0xac00 && code <= 0xd7a3;
  return isHangul && (code - 0xac00) % 28 === 0 ? "예요" : "이에요";
}

// 목록이 이보다 길면 메뉴를 하나씩 읽지 않고, 화면을 보고 번호나 이름을 말하라고만 안내한다
const MAX_SPOKEN_ITEMS = 4;

function longListSpeech(text: string, count: number): string {
  const first = text.split("\n").map((l) => l.trim()).find((l) => l && !/^\d+\s*(?:번|\.)\s*\S/.test(l)) ?? "";
  const intro = first.split(/(?<=[.!?。])\s+/)[0]?.replace(/[?？]$/, "").trim();
  const head = intro && intro.length <= 60 ? intro.replace(/[.。]?$/, ".") : `메뉴가 ${count}가지 있어요.`;
  return `${head} 화면을 보시고 번호나 이름으로 말씀해 주세요.`;
}

export function summarizeForSpeech(text: string, recommended?: string[]): string {
  text = text.replace(/\*\*/g, ""); // 말풍선용 굵게 표시(**…**)는 소리로 읽지 않는다
  if (recommended && recommended.length > MAX_SPOKEN_ITEMS) {
    return longListSpeech(text, recommended.length);
  }
  if (recommended && recommended.length > 0) {
    const list = recommended.map((m, i) => `${i + 1}번 ${m}`).join(", ");
    return `추천 메뉴는 ${list}예요. 원하시는 번호를 말씀해 주세요.`;
  }

  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const numbered = lines.filter((l) => /^\d+\s*(?:번|\.)\s*\S/.test(l));
  if (numbered.length > MAX_SPOKEN_ITEMS) {
    return longListSpeech(text, numbered.length);
  }
  if (numbered.length >= 2) {
    const names = numbered.map((l) =>
      l.replace(/^\d+\s*(?:번|\.)\s*/, "").split(/[:(]/)[0].trim()
    );
    const intro = lines.find((l) => !numbered.includes(l)) ?? "";
    const head = intro.replace(/[.。]$/, "");
    const list = names.join(", ");
    return `${head ? head + ". " : ""}${list}${copula(list)}. 화면에서 자세히 확인해 주세요.`.slice(0, 200);
  }

  const spoken = text
    .split(/(?<=[.!?。])\s+/)
    .filter((sent) => !/\d\)\s/.test(sent))
    .join(" ");

  const plain = spoken
    .replace(/\s*\([^)]*\)/g, "")
    .replace(/[×*#`]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const sentences = plain.split(/(?<=[.!?。])\s+/);
  // 끝 문장이 "결제할까요?", "더 필요한 건 없으세요?"처럼 핵심 안내라서 항상 끝까지 읽는다
  if (sentences.length <= 2) {
    const all = sentences.join(" ");
    return all.length <= MAX_SPEECH_CHARS * 1.5 ? all : `${sentences[0].slice(0, MAX_SPEECH_CHARS)} ${sentences[sentences.length - 1]}`.trim();
  }
  const last = sentences[sentences.length - 1];
  // 끝 두 문장이 "질문 + 안내"("…요청사항 있으세요? 없으면 '없어요'라고 말씀해 주세요.")면 둘 다 읽는다
  const prev = sentences[sentences.length - 2];
  const tail = /[?？]$/.test(prev) ? `${prev} ${last}` : last;
  return `${sentences[0].slice(0, Math.max(40, MAX_SPEECH_CHARS - tail.length))} ${tail}`.trim();
}

export const GREETING_TEXT =
  "안녕하세요! 말로 주문하는 음성 주문 도우미 키오예요. 어떤 음료 드릴까요?";
export const GREETING_SPEECH =
  "안녕하세요! 말로 주문하는 음성 주문 도우미 키오예요. 어떤 음료 드릴까요?";
export const GREETING_EXAMPLES = ["아이스 아메리카노 두 잔 주세요", "달달한 거 추천해줘", "카드로 결제할게요"];
