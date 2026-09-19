import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { AssistantButton } from "./components/AssistantButton";
import { useMenuStore } from "./store/menuStore";

export default function App() {
  const fetchMenus = useMenuStore((s) => s.fetchMenus);

  useEffect(() => {
    fetchMenus();
    const timer = setInterval(fetchMenus, 10000);
    return () => clearInterval(timer);
  }, [fetchMenus]);

  return (
    <div className="min-h-screen w-full bg-[#FFEFCE]">
      <AssistantButton />
      <div className="w-full min-h-screen flex flex-col">
        <Outlet />
      </div>
    </div>
  );
}
