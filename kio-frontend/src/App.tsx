import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { AssistantButton } from "./components/AssistantButton";
import { useMenuStore } from "./store/menuStore";
import { useDiscountStore } from "./store/discountStore";

export default function App() {
  const fetchMenus = useMenuStore((s) => s.fetchMenus);
  const fetchDiscounts = useDiscountStore((s) => s.fetchDiscounts);

  useEffect(() => {
    fetchMenus();
    const timer = setInterval(fetchMenus, 10000);
    return () => clearInterval(timer);
  }, [fetchMenus]);

  useEffect(() => {
    fetchDiscounts();
    const timer = setInterval(fetchDiscounts, 10000);
    return () => clearInterval(timer);
  }, [fetchDiscounts]);

  return (
    <div className="min-h-screen w-full bg-[#FFEFCE]">
      <AssistantButton />
      <div className="w-full min-h-screen flex flex-col">
        <Outlet />
      </div>
    </div>
  );
}
