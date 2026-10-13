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
export function toSpoken(text: string): string {
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

function speakWithBrowser(text: string, mine: number, onDone?: () => void) {
  if (!ttsSupported) {
    onDone?.();
    return;
  }
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ko-KR";
  u.rate = 0.9;
  if (koVoice) u.voice = koVoice;
  const done = () => {
    if (mine === generation) onDone?.();
  };
  u.onend = done;
  u.onerror = done;
  window.speechSynthesis.speak(u);
}

async function fetchServerAudio(text: string, signal: AbortSignal): Promise<string | null> {
  const cached = audioCache.get(text);
  if (cached) return cached;
  const timeout = setTimeout(() => abort?.abort(), 8000);
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal,
    });
    if (!res.ok) return null;
    const url = URL.createObjectURL(await res.blob());
    if (audioCache.size < 50) audioCache.set(text, url);
    return url;
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

export async function speak(rawText: string, onDone?: () => void) {
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
        if (mine === generation) speakWithBrowser(text, mine, onDone);
      };
      try {
        await a.play();
        return;
      } catch {
      }
    } else {
      serverRetryAt = Date.now() + 60_000;
    }
    if (mine !== generation) return;
  }
  speakWithBrowser(text, mine, onDone);
}

const MAX_SPEECH_CHARS = 110;

function copula(word: string): string {
  const code = word.trim().charCodeAt(word.trim().length - 1);
  const isHangul = code >= 0xac00 && code <= 0xd7a3;
  return isHangul && (code - 0xac00) % 28 === 0 ? "예요" : "이에요";
}

export function summarizeForSpeech(text: string, recommended?: string[]): string {
  if (recommended && recommended.length > 0) {
    const list = recommended.map((m, i) => `${i + 1}번 ${m}`).join(", ");
    return `추천 메뉴는 ${list}예요. 원하시는 번호를 말씀해 주세요.`;
  }

  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const numbered = lines.filter((l) => /^\d+\s*(?:번|\.)\s*\S/.test(l));
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
  let out = sentences.slice(0, 2).join(" ");
  if (out.length > MAX_SPEECH_CHARS) out = sentences[0].slice(0, MAX_SPEECH_CHARS);
  return out;
}

export const GREETING_TEXT =
  "안녕하세요! 저는 키오예요. 마시고 싶은 메뉴를 편하게 말씀해 주세요.";
export const GREETING_SPEECH =
  "안녕하세요, 저는 키오예요. 마시고 싶은 메뉴를 편하게 말씀해 주세요. 마이크 버튼을 누르고 말씀하시면 돼요.";
export const GREETING_EXAMPLES = ["아이스 아메리카노 두 잔 주세요", "달달한 거 추천해줘", "카드로 결제할게요"];
