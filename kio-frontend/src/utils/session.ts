// 손님(키오스크 한 번 사용)별 대화 구분값. 서버가 '다른 거 없어?', '이걸로 줘' 같은 이어 말하기를 이 값으로 구분해 기억한다.
// 탭(키오스크 화면) 하나마다 따로 만들고, 처음 화면(Splash)으로 돌아오면 새 손님으로 보고 새로 만든다.
const KEY = "kio_session_id";

function makeId(): string {
  const rnd =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `kio-${rnd}`;
}

let memoryId = "";

// 지금 세션 id (없으면 만든다). sessionStorage 를 못 쓰는 환경이어도 메모리에 들고 있는다.
export function getSessionId(): string {
  try {
    const saved = sessionStorage.getItem(KEY);
    if (saved) return saved;
    const id = memoryId || makeId();
    sessionStorage.setItem(KEY, id);
    return id;
  } catch {
    return memoryId || (memoryId = makeId());
  }
}

// 새 손님 시작: 새 id 로 바꾼다(서버의 이전 대화 상태는 더 이상 쓰이지 않는다).
export function startNewSession(): string {
  const id = makeId();
  memoryId = id;
  try {
    sessionStorage.setItem(KEY, id);
  } catch {
    /* 저장소를 못 써도 메모리 값으로 동작 */
  }
  return id;
}
