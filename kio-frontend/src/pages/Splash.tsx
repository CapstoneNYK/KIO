import { LuCoffee } from "react-icons/lu";
import { useNavigate } from "react-router-dom";

export const Splash = () => {
  const navigate = useNavigate();

  const handleTouch = () => {
    navigate("/home");
  };

  return (
    <div
      className="relative flex min-h-screen w-full items-center justify-center overflow-hidden "
      onClick={handleTouch}
    >
      <div className="relative z-10 flex flex-col items-center text-center text-white">
        <LuCoffee className="mb-6 h-16 w-16  drop-shadow-md sm:h-20 sm:w-20" />

        <p className="text-5xl font-extrabold tracking-widest drop-shadow-md sm:text-5xl">
          NYK
        </p>
        <p className="mb-6 text-5xl font-extrabold tracking-widest drop-shadow-md sm:text-5xl">
          CAFE
        </p>

        <p className="text-lg font-medium text-black/80 sm:text-xl">
          화면을 터치해주세요.
        </p>
      </div>
    </div>
  );
};
