"""어르신 말투 무작위 주문 시뮬레이션 (정답을 아는 주문을 여러 말투로 바꿔 대화 끝까지 돌려 본다).

  python -m eval.sim_fuzz            # 400건, 시드 고정
  python -m eval.sim_fuzz -n 1000 -s 7
"""
import random
import re
import sys

from eval.sim_elder import Kiosk  # 같은 폴더의 시뮬레이터 (LLM 대체 분류 포함)

N = 400
SEED = 1
NOISE_RATE = 0.2
if "-n" in sys.argv:
    N = int(sys.argv[sys.argv.index("-n") + 1])
if "-s" in sys.argv:
    SEED = int(sys.argv[sys.argv.index("-s") + 1])

# (말하는 법들, 정식 이름, 카테고리, 온도 선택 가능 여부)
MENUS = [
    (["아아", "아이스 아메리카노", "아메리카노", "아메리카노 아이스"], "아메리카노", "coffee", True),
    (["카페라떼", "카페 라떼", "라떼", "까페라떼"], "카페라떼", "coffee", True),
    (["카푸치노", "카푸치 노", "카푸치도"], "카푸치노", "coffee", True),
    (["바닐라라떼", "바닐라 라떼"], "바닐라라떼", "coffee", True),
    (["카라멜 마키아토", "카라멜마끼아또"], "카라멜마키아토", "coffee", True),
    (["에스프레소"], "에스프레소", "coffee", False),
    (["디카페인 라떼"], "디카페인 라떼", "coffee", True),
    (["얼그레이", "캐모마일", "페퍼민트"], None, "tea", True),
    (["딸기 스무디", "블루베리 스무디"], None, "other", False),
    (["레몬에이드", "자몽 에이드", "청포도 에이드"], None, "other", False),
    (["오렌지 주스", "오렌지 쥬스", "망고 주스"], None, "other", False),
]
CANON = {"아아": "아메리카노", "아이스 아메리카노": "아메리카노", "아메리카노 아이스": "아메리카노", "카페 라떼": "카페라떼",
         "라떼": "카페라떼", "까페라떼": "카페라떼", "카푸치 노": "카푸치노", "카푸치도": "카푸치노",
         "바닐라 라떼": "바닐라라떼", "카라멜마끼아또": "카라멜마키아토", "카라멜 마키아토": "카라멜마키아토",
         "레몬에이드": "레몬 에이드", "오렌지 쥬스": "오렌지 주스"}
QTY = [(1, ["한 잔", "하나", "한잔", "1잔", "한 개"]), (2, ["두 잔", "둘", "2잔", "두 개", "두잔"]), (3, ["세 잔", "3잔", "세 개"])]
TEMP = [("HOT", ["따뜻한", "따뜻하게", "뜨거운 걸로", "따듯한", "핫"]), ("ICE", ["아이스", "차가운", "시원한", "차갑게", "아이스로"])]
FILL = ["", "", "저기요 ", "음 ", "어 그 ", "여기 ", "아 "]
END = ["주세요", "줘", "주세여", "주쇼", "부탁해요", "주실래요", "줘요", ""]


def say_order(rng):
    surface, canon, cat, temp_ok = rng.choice(MENUS)
    form = rng.choice(surface)
    name = canon or CANON.get(form, form)
    if name == "아메리카노" and form in ("아아", "아이스 아메리카노", "아메리카노 아이스"):
        temp, temp_said = "ICE", form != "아메리카노"
    else:
        temp, temp_said = None, False
    qty, qtxts = rng.choice(QTY)
    qtxt = rng.choice(qtxts)
    shot = light = 0
    if cat == "coffee" and rng.random() < 0.25:
        shot = rng.choice([1, 2])
    if cat == "tea" and rng.random() < 0.15:
        shot = 1
    if cat == "coffee" and rng.random() < 0.15:
        light = 1
    if not temp_ok:
        want_temp = "HOT" if cat == "coffee" else "ICE"
    else:
        want_temp = temp
        if want_temp is None:
            want_temp, tw = rng.choice(TEMP)
            tw = rng.choice(tw)
            if rng.random() < 0.55:  # 처음 문장에서 온도를 말함
                form = f"{tw} {form}"
                temp_said = True
        elif temp_said:
            pass
    if cat in ("other",) and not temp_said:
        want_temp = "ICE"
    parts = [form]
    opt = []
    if shot:
        opt.append("샷 추가" if shot == 1 else rng.choice(["샷 추가 두 번", "샷 두 번 추가", "샷 2번 추가"]))
    if light:
        opt.append("연하게")
    text = f"{rng.choice(FILL)}{form} {' '.join(opt)} {qtxt} {rng.choice(END)}".replace("  ", " ").strip()
    options = []
    if shot:
        options.append("샷추가" + ("×2" if shot == 2 else ""))
    if light:
        options.append("연하게")
    return text, (name, want_temp, qty, tuple(sorted(options))), temp_said, temp_ok, cat, bool(shot), bool(light)


_last_name = [None]


def respond(bot: str, wants: dict, rng):
    """봇 질문에 정답에 맞게 어르신처럼 답한다 (여러 메뉴면 지금 묻는 메뉴에 맞춰)."""
    pos = {n: m.start() for n in wants for m in re.finditer(re.escape(n) + r"[은는] 따뜻하게 드릴까요", bot)}
    name = max(pos, key=pos.get) if pos else (_last_name[0] if _last_name[0] in wants else next(iter(wants)))
    _last_name[0] = name
    _, temp, qty, options = wants[name]
    if "따뜻하게 드릴까요" in bot:
        return rng.choice(["따뜻하게요", "뜨거운 걸로", "따듯하게 주세요", "핫으로"]) if temp == "HOT" else \
            rng.choice(["차갑게요", "아이스로 주세요", "시원한 걸로", "차가운 걸로 주세요"])
    if "샷 추가해드릴까요" in bot:
        shots = [o for o in options if o.startswith("샷추가")]
        return "네" if shots else rng.choice(["아니요", "아뇨", "괜찮아요", "안 해도 돼요"])
    if "몇 샷" in bot:
        return "두 번이요" if any("×2" in o for o in options) else rng.choice(["한 번", "한 번이요", "하나요"])
    if "연하게 드릴까요" in bot:
        return "네" if "연하게" in options else rng.choice(["아니요", "아뇨", "괜찮아요"])
    if "장바구니에 담았습니다" in bot:  # 질문 없이 바로 담긴 주문
        return "결제할게요"
    if "더 주문하실" in bot or "더 필요한 건" in bot:
        return rng.choice(["없어요", "그게 다예요", "괜찮아요", "이게 다예요"])
    return None


NOISE = ["뭐라고요?", "음...", "잠깐만요", "다시 말해줘", "네?", "글쎄요 뭐였더라"]


def run_one(rng):
    n_items = 2 if rng.random() < 0.3 else 1
    items = []
    while len(items) < n_items:
        text, want, temp_said, temp_ok, cat, shot, light = say_order(rng)
        if any(w[0] == want[0] for _, w, *_ in items):  # 같은 메뉴가 겹치면 다시 뽑는다
            continue
        items.append((text, want, temp_said, temp_ok))
    if n_items == 1:
        text = items[0][0]
    else:  # 이음말로 이어 말하기 (잔 수 말 뒤에 이음말)
        glue = rng.choice([" 그리고 ", " 하고 ", " 랑 ", ", "])
        clean = [re.sub(r"^(?:저기요|음|어 그|여기|아) ", "", t) for t, *_ in items]
        clean = [re.sub(r" (?:주세요|줘|주세여|주쇼|부탁해요|주실래요|줘요)$", "", t) for t in clean]
        text = glue.join(clean) + " " + rng.choice(["주세요", "줘", "부탁해요", ""])
        text = text.strip()
    wants = {w[0]: w for _, w, *_ in items}
    k = Kiosk()
    msgs = [text]
    k.say(text)
    for _ in range(20):
        if k.paid or not k.log:
            break
        bot = k.log[-1][1]
        ans = respond(bot, wants, rng)
        if ans is None:
            break
        if rng.random() < NOISE_RATE and ("드릴까요" in bot or "몇 샷" in bot):
            k.say(rng.choice(NOISE))  # 못 알아듣거나 되묻는 말을 먼저 한 번
            bot = k.log[-1][1]
            ans = respond(bot, wants, rng) or ans
        msgs.append(ans)
        k.say(ans)
    got = sorted(k.cart_view())
    exp = sorted((n, t, q, o) for n, t, q, o in wants.values())
    # 온도를 고를 수 없는 메뉴는 온도 비교 제외
    def loose(rows, ref):
        out = []
        for r in rows:
            temp_ok = next((it[3] for it in items if it[1][0] == r[0]), True)
            out.append((r[0], r[1] if temp_ok else "-", r[2], r[3]))
        return sorted(out)
    ok = loose(got, wants) == loose(exp, wants)
    return ok, text, exp, got, k.log, k.paid


def main():
    rng = random.Random(SEED)
    bad = []
    for _ in range(N):
        ok, text, want, got, log, paid = run_one(rng)
        if not (ok and paid):
            bad.append((text, want, got, log, paid))
    print(f"무작위 주문 {N - len(bad)}/{N} 정상 (시드 {SEED})")
    for text, want, got, log, paid in bad[:25]:
        print(f"\n✗ {text}\n   기대 {want}\n   결과 {got} 결제이동 {paid}")
        for u, a in log:
            print(f"   🧓 {u}\n   🤖 {a[:90]}")
    return len(bad)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
