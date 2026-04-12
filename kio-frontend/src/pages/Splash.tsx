import { LuCoffee } from "react-icons/lu";
import { useNavigate } from "react-router-dom";

export const Splash = () => {
  const navigate = useNavigate();

  return (
    <div
      className="relative flex h-screen w-full items-center justify-center overflow-hidden cursor-pointer"
      style={{ backgroundColor: "#FFEFCE" }}
      onClick={() => navigate("/home")}
    >
      {/* 우상단동그라미 */}
      <div className="absolute rounded-full bg-[#FFD97D] w-[420px] h-[420px] -top-[70px] -right-[50px] opacity-80" />
      {/* 좌중단동그라미 */}
      <div className="absolute rounded-full bg-[#FFD97D] w-[310px] h-[310px] top-[30%] -left-[60px] opacity-60" />
      {/* 하단동그라미 */}
      <div className="absolute rounded-full bg-[#FFD97D] w-[300px] h-[300px] bottom-[6%] right-[15%]" />

      {/* 중앙 콘텐츠 */}
      <div className="relative z-10 flex flex-col items-center text-center">
        <LuCoffee className="mb-6 h-20 w-20 text-white drop-shadow-md" />
        <p className="text-6xl font-extrabold tracking-widest text-white drop-shadow-md leading-tight">
          NYK
        </p>
        <p className="text-6xl font-extrabold tracking-widest text-white drop-shadow-md leading-tight mb-10">
          CAFE
        </p>
        <p className="text-xl font-medium" style={{ color: "#8B6914" }}>
          화면을 터치해주세요.
        </p>
      </div>
    </div>
  );
};
