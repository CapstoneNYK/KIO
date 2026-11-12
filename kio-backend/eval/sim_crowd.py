"""카페 현장 스트레스 테스트: 손님 유형별로 세션 전체를 무작위로 만들어 끝까지 돌려 본다.

  python -m eval.sim_crowd            # 유형별 150세션
  python -m eval.sim_crowd -n 400 -s 3

유형: 단체(3~6명이 차례로 주문), 바쁜 직장인(한 문장에 결제), 소음(엉뚱한 말·되묻기 섞임), 변덕(중간에 한 잔 취소)
정답을 아는 주문만 만들고, 장바구니와 결제 이동 여부를 비교한다.
"""
import random
import re
import sys

from eval import sim_fuzz as F
from eval.sim_elder import Kiosk

N = int(sys.argv[sys.argv.index("-n") + 1]) if "-n" in sys.argv else 150
SEED = int(sys.argv[sys.argv.index("-s") + 1]) if "-s" in sys.argv else 1

JUNK = ["어어어", "여보 뭐 먹을래", "아 의자가 낮네", "오늘 날씨가 좋네", "...", "잠깐만", "뭐라고요?", "음...", "네?"]
PAY = ["결제할게요", "계산해 주세요", "카드로 결제할게요", "결제"]


def new_order(rng, used):
    for _ in range(50):
        text, want, temp_said, temp_ok, cat, shot, light = F.say_order(rng)
        if want[0] not in used:
            used.add(want[0])
            return text, want, temp_ok
    raise RuntimeError


def finish_dialog(k, wants, rng, noise):
    """봇이 질문하는 동안 정답대로 답한다. 소음이면 가끔 엉뚱한 말을 먼저 한다."""
    for _ in range(20):
        if not k.log:
            return
        bot = k.log[-1][1]
        if "더 주문하실" in bot or "장바구니에 담았습니다" in bot:
            return
        ans = F.respond(bot, wants, rng)
        if ans is None:
            return
        if noise and rng.random() < 0.3 and "드릴까요" in bot:
            k.say(rng.choice(JUNK))
            bot = k.log[-1][1]
            ans = F.respond(bot, wants, rng) or ans
        k.say(ans)


def group(rng):
    k, wants_all, used = Kiosk(), {}, set()
    for _ in range(rng.randint(3, 6)):
        text, want, temp_ok = new_order(rng, used)
        wants_all[want[0]] = (want, temp_ok)
        k.say(text)
        finish_dialog(k, {want[0]: want}, rng, noise=rng.random() < 0.3)
        if k.log and "더 주문하실" in k.log[-1][1] and rng.random() < 0.5:
            pass  # 다음 사람이 바로 이어서 말함 (더 주문 단계에서 새 메뉴)
    return k, wants_all, None


def busy(rng):
    k, used = Kiosk(), set()
    text, want, temp_ok = new_order(rng, used)
    # 문장 끝에 결제를 붙여 한 번에 말한다 (온도·옵션을 모두 말한 경우만 기대와 일치하므로 온도 안 말하면 기본값 허용)
    k.say(re.sub(r"\s*(주세요|줘|주세여|주쇼|부탁해요|주실래요|줘요)?$", "", text) + " " + rng.choice(PAY))
    return k, {want[0]: (want, temp_ok)}, "loose"


def noisy(rng):
    k, used = Kiosk(), set()
    text, want, temp_ok = new_order(rng, used)
    for _ in range(rng.randint(1, 3)):
        k.say(rng.choice(JUNK))
    k.say(text)
    finish_dialog(k, {want[0]: want}, rng, noise=True)
    return k, {want[0]: (want, temp_ok)}, None


def fickle(rng):
    k, used, wants_all = Kiosk(), set(), {}
    t1, w1, ok1 = new_order(rng, used)
    t2, w2, ok2 = new_order(rng, used)
    for t, w, ok in ((t1, w1, ok1), (t2, w2, ok2)):
        k.say(t)
        finish_dialog(k, {w[0]: w}, rng, noise=False)
        wants_all[w[0]] = (w, ok)
    k.say(f"{w2[0]} 빼줘")  # 마지막 메뉴 취소
    del wants_all[w2[0]]
    return k, wants_all, "cancel"


def run(kind, fn, rng):
    k, wants_all, mode = fn(rng)
    if mode != "loose" and not k.paid:
        if k.log and ("더 주문하실" in k.log[-1][1] or "장바구니에 담았습니다" in k.log[-1][1] or mode == "cancel"):
            k.say(rng.choice(PAY))
    got = sorted((n, t if wants_all[n][1] else "-", q, o) for n, t, q, o in k.cart_view())
    exp = sorted((w[0], w[1] if ok else "-", w[2], w[3]) for w, ok in wants_all.values())
    if mode == "loose":  # 온도를 안 말하면 기본값(아이스)으로 담김 → 온도는 비교하지 않는다
        got = [(a, "-", c, d) for a, b, c, d in got]
        exp = [(a, "-", c, d) for a, b, c, d in exp]
    # 질문 없이 '담았습니다'로 끝난 경우: 어르신이 결제를 말한 것으로 본다
    ok = got == exp and k.paid
    return ok, got, exp, k


def main():
    rng = random.Random(SEED)
    total_bad = 0
    for kind, fn in (("단체 손님", group), ("바쁜 직장인", busy), ("소음·되묻기", noisy), ("변덕(취소)", fickle)):
        bad = []
        for _ in range(N):
            ok, got, exp, k = run(kind, fn, rng)
            if not ok:
                bad.append((got, exp, k))
        total_bad += len(bad)
        print(f"{kind}: {N - len(bad)}/{N}")
        for got, exp, k in bad[:6]:
            print(f"   ✗ 기대 {exp}\n     결과 {got} 결제 {k.paid}")
            for u, a in k.log:
                print(f"     🧓 {u}\n     🤖 {a[:80]}")
    return total_bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
