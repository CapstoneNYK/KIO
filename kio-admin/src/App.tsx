import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { SalesStatus } from "./pages/SalesStatus";
import { MenuAnalytics } from "./pages/MenuAnalytics";
import { OrderHistory } from "./pages/OrderHistory";
import { MenuManagement } from "./pages/MenuManagement";

export type PageId = "sales" | "analytics" | "orders" | "menus";

function App() {
  const [activePage, setActivePage] = useState<PageId>("sales");

  const PAGE_TITLES: Record<PageId, string> = {
    sales: "매출 현황",
    analytics: "메뉴 분석",
    orders: "주문 내역",
    menus: "메뉴 관리",
  };

  return (
    <div className="flex h-screen" style={{ backgroundColor: "#F8F7F5" }}>
      <Sidebar activePage={activePage} onSelect={setActivePage} />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b px-8 flex items-center justify-between flex-shrink-0" style={{ borderColor: "#FEE685", height: "68px" }}>
          <h1 className="text-xl font-black text-gray-900">{PAGE_TITLES[activePage]}</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">2026년 9월 14일</span>
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white" style={{ backgroundColor: "#F5A623" }}>
              관
            </div>
          </div>
        </header>
        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {activePage === "sales" && <SalesStatus />}
          {activePage === "analytics" && <MenuAnalytics />}
          {activePage === "orders" && <OrderHistory />}
          {activePage === "menus" && <MenuManagement />}
        </main>
      </div>
    </div>
  );
}

export default App;
