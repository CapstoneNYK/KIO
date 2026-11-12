import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { tpass_poster, t_poster, kt_poster, cafe_logo } from "../assets";
import { useDiscountStore } from "../store/discountStore";
import { useChatPrefs } from "../store/chatPrefsStore";

const FALLBACK_POSTERS = [tpass_poster, t_poster, kt_poster];
const SLIDE_INTERVAL = 3500;

export const Splash = () => {
  const navigate = useNavigate();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [transitionEnabled, setTransitionEnabled] = useState(true);
  const fetchedPosters = useDiscountStore((s) => s.posters);
  const postersLoading = useDiscountStore((s) => s.loading);

  const POSTERS = useMemo(
    () => (fetchedPosters.length > 0 ? fetchedPosters.map((p) => p.url) : FALLBACK_POSTERS),
    [fetchedPosters]
  );
  const EXTENDED_POSTERS = useMemo(() => [...POSTERS, POSTERS[0]], [POSTERS]);

  // 포스터 개수가 바뀌면(서버에서 받아 오면) 처음 장부터 다시 보여 준다
  const [postersCount, setPostersCount] = useState(POSTERS.length);
  if (postersCount !== POSTERS.length) {
    setPostersCount(POSTERS.length);
    setCurrentIndex(0);
  }

  useEffect(() => {
    if (postersLoading) return;
    const timer = setInterval(() => {
      setCurrentIndex((prev) => prev + 1);
    }, SLIDE_INTERVAL);
    return () => clearInterval(timer);
  }, [postersLoading, POSTERS.length]);

  useEffect(() => {
    if (currentIndex === POSTERS.length) {
      const timeout = setTimeout(() => {
        setTransitionEnabled(false);
        setCurrentIndex(0);
      }, 500);
      return () => clearTimeout(timeout);
    }
  }, [currentIndex, POSTERS.length]);

  useEffect(() => {
    if (!transitionEnabled) {
      const timeout = setTimeout(() => setTransitionEnabled(true), 50);
      return () => clearTimeout(timeout);
    }
  }, [transitionEnabled]);

  const dotIndex = currentIndex % POSTERS.length;
  const openChat = useChatPrefs((s) => s.openChat);

  const startVoice = () => {
    navigate("/home");
    openChat();
  };

  return (
    <div
      className="relative flex flex-col h-dvh w-full overflow-hidden"
      style={{ backgroundColor: "#FFEFCE" }}
    >
      <div className="relative z-10 flex items-center justify-center gap-4 pt-6 pb-3 shrink-0">
        <img src={cafe_logo} alt="NYK CAFE" className="h-14 w-auto" />
      </div>

      <div className="relative z-10 flex flex-1 min-h-0 flex-col items-center justify-center px-8 py-2">
        <div className="w-full max-w-lg flex-1 min-h-0 overflow-hidden">
          <div
            className="flex h-full"
            style={{
              transform: `translateX(-${currentIndex * 100}%)`,
              transition: transitionEnabled
                ? "transform 500ms ease-in-out"
                : "none",
            }}
          >
            {EXTENDED_POSTERS.map((poster, index) => (
              <div key={index} className="flex h-full w-full shrink-0 items-center justify-center">
                <img
                  src={poster}
                  alt={`포스터 ${(index % POSTERS.length) + 1}`}
                  className="max-h-full max-w-full rounded-3xl object-contain shadow-2xl"
                  draggable={false}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 mt-4">
          {POSTERS.map((_, index) => (
            <button
              key={index}
              onClick={() => setCurrentIndex(index)}
              className={`h-2.5 rounded-full transition-all duration-300 ${
                index === dotIndex
                  ? "w-7 bg-yellow-400"
                  : "w-2.5 bg-[#D4A64A] opacity-60"
              }`}
            />
          ))}
        </div>
      </div>

      <div className="relative z-10 flex gap-4 px-8 pb-10 pt-4 shrink-0">
        <button
          onClick={startVoice}
          className="flex flex-1 flex-col items-center justify-center gap-1 py-5 rounded-3xl active:scale-95 transition-transform bg-[#F5A623]"
        >
          <span className="text-3xl font-black text-white">음성주문</span>
          <span className="text-sm font-medium text-white opacity-80">
            말로 편하게 주문
          </span>
        </button>
        <button
          onClick={() => navigate("/home")}
          className="flex flex-1 flex-col items-center justify-center gap-1 py-5 rounded-3xl active:scale-95 transition-transform bg-[#FCC200]"
        >
          <span className="text-3xl font-black text-white">화면주문</span>
          <span className="text-sm font-medium text-white opacity-80">
            메뉴를 눌러서 주문
          </span>
        </button>
      </div>
    </div>
  );
};
