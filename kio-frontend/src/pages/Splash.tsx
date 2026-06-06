import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { tpass_poster, t_poster, kt_poster, cafe_logo } from "../assets";

const POSTERS = [tpass_poster, t_poster, kt_poster];
const SLIDE_INTERVAL = 3500;
const EXTENDED_POSTERS = [...POSTERS, POSTERS[0]];

export const Splash = () => {
  const navigate = useNavigate();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [transitionEnabled, setTransitionEnabled] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentIndex((prev) => prev + 1);
    }, SLIDE_INTERVAL);
    return () => clearInterval(timer);
  }, []);

  // 복제 슬라이드(index 3)에 도달하면 애니메이션 후 조용히 0으로 초기화
  useEffect(() => {
    if (currentIndex === POSTERS.length) {
      const timeout = setTimeout(() => {
        setTransitionEnabled(false);
        setCurrentIndex(0);
      }, 500);
      return () => clearTimeout(timeout);
    }
  }, [currentIndex]);

  // transition 비활성화 후 다음 틱에 다시 활성화
  useEffect(() => {
    if (!transitionEnabled) {
      const timeout = setTimeout(() => setTransitionEnabled(true), 50);
      return () => clearTimeout(timeout);
    }
  }, [transitionEnabled]);

  const dotIndex = currentIndex % POSTERS.length;

  return (
    <div
      className="relative flex flex-col h-screen w-full overflow-hidden"
      style={{ backgroundColor: "#FFEFCE" }}
    >
      <div className="relative z-10 flex items-center justify-center gap-4 pt-6 pb-3 shrink-0">
        <img src={cafe_logo} alt="NYK CAFE" className="h-14 w-auto" />
      </div>

      {/* 포스터 슬라이드 */}
      <div className="relative z-10 flex flex-1 min-h-0 flex-col items-center justify-center px-8 py-2">
        <div className="w-full max-w-lg overflow-hidden rounded-3xl shadow-2xl">
          <div
            className="flex"
            style={{
              transform: `translateX(-${currentIndex * 100}%)`,
              transition: transitionEnabled
                ? "transform 500ms ease-in-out"
                : "none",
            }}
          >
            {EXTENDED_POSTERS.map((poster, index) => (
              <img
                key={index}
                src={poster}
                alt={`포스터 ${(index % POSTERS.length) + 1}`}
                className="w-full shrink-0 object-cover"
                draggable={false}
              />
            ))}
          </div>
        </div>

        {/* 도트 인디케이터 */}
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

      {/* 하단 주문 유형 버튼 */}
      <div className="relative z-10 flex gap-4 px-8 pb-10 pt-4 shrink-0">
        <button
          onClick={() => navigate("/home", { state: { orderType: "eat-in" } })}
          className="flex flex-1 flex-col items-center justify-center gap-1 py-5 rounded-3xl active:scale-95 transition-transform bg-[#F5A623]"
        >
          <span className="text-3xl font-black text-white">먹고가기</span>
          <span className="text-sm font-medium text-white opacity-80">
            매장 내 식사
          </span>
        </button>
        <button
          onClick={() =>
            navigate("/home", { state: { orderType: "take-out" } })
          }
          className="flex flex-1 flex-col items-center justify-center gap-1 py-5 rounded-3xl active:scale-95 transition-transform bg-[#FCC200]"
        >
          <span className="text-3xl font-black text-white">가져가기</span>
          <span className="text-sm font-medium text-white opacity-80">
            포장 주문
          </span>
        </button>
      </div>
    </div>
  );
};
