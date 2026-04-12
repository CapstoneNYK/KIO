import { Outlet } from "react-router-dom";
import { logo } from "./assets";

export default function App() {
  return (
    <div className="min-h-screen w-full bg-[#FFEFCE]">
      <img
        src={logo}
        alt="KIO"
        className="fixed top-4 right-4 w-20 h-20 rounded-full z-9999 pointer-events-none"
      />
      <div className="w-full min-h-screen flex flex-col">
        <Outlet />
      </div>
    </div>
  );
}
