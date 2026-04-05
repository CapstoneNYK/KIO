import { GoHome } from "react-icons/go";
import { logo } from "../assets";

export const TopBar = () => {
  return (
    <header className="w-full bg-[#FFF9F1] px-4 sm:px-6 lg:px-8">
      <div className="relative flex h-14 sm:h-16 items-center justify-between">
        <button className="flex items-center gap-2 text-gray-600 hover:text-gray-800 transition">
          <GoHome className="w-5 h-5 sm:w-6 sm:h-6" />
          <span className="text-sm sm:text-base font-medium">처음으로</span>
        </button>

        <h1
          className="absolute left-1/2 -translate-x-1/2
                       text-lg sm:text-xl lg:text-2xl
                       font-semibold text-gray-900"
        >
          Menu
        </h1>

        <div className="flex items-center">
          <img
            src={logo}
            alt="KIO logo"
            className="h-8 w-8 sm:h-10 sm:w-10 rounded-full"
          />
        </div>
      </div>
    </header>
  );
};
