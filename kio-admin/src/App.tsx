import { useEffect, useState } from "react";
import { PiListBold, PiSignOutBold } from "react-icons/pi";
import { Sidebar } from "./components/Sidebar";
import { SalesStatus } from "./pages/SalesStatus";
import { MenuAnalytics } from "./pages/MenuAnalytics";
import { OrderHistory } from "./pages/OrderHistory";
import { MenuManagement } from "./pages/MenuManagement";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { clearToken, getToken, getUsername, UNAUTHORIZED_EVENT } from "./api";

export type PageId = "sales" | "analytics" | "orders" | "menus";
type AuthView = "login" | "signup";

const formatToday = () =>
  new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" });

function App() {
  const [activePage, setActivePage] = useState<PageId>("sales");
  const [isAuthed, setIsAuthed] = useState(() => !!getToken());
  const [authView, setAuthView] = useState<AuthView>("login");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const username = getUsername() ?? "관리자";

  useEffect(() => {
    const handleUnauthorized = () => setIsAuthed(false);
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  const handleLogout = () => {
    clearToken();
    setIsAuthed(false);
    setAuthView("login");
  };

  const PAGE_TITLES: Record<PageId, string> = {
    sales: "매출 현황",
    analytics: "메뉴 분석",
    orders: "주문 내역",
    menus: "메뉴 관리",
  };

  if (!isAuthed) {
    return authView === "login" ? (
      <Login onSuccess={() => setIsAuthed(true)} onGoToSignup={() => setAuthView("signup")} />
    ) : (
      <Signup onSuccess={() => setIsAuthed(true)} onGoToLogin={() => setAuthView("login")} />
    );
  }

  return (
    <div className="flex h-screen" style={{ backgroundColor: "#F8F7F5" }}>
      <Sidebar
        activePage={activePage}
        onSelect={(page) => { setActivePage(page); setSidebarOpen(false); }}
        username={username}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b px-4 sm:px-8 flex items-center justify-between flex-shrink-0" style={{ borderColor: "#FEE685", height: "68px" }}>
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden text-gray-500 hover:text-gray-800 transition-colors"
              aria-label="메뉴 열기"
            >
              <PiListBold size={22} />
            </button>
            <h1 className="text-xl font-black text-gray-900 truncate">{PAGE_TITLES[activePage]}</h1>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="hidden sm:inline text-sm text-gray-400">{formatToday()}</span>
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white uppercase"
              style={{ backgroundColor: "#F5A623" }}
              title={username}
            >
              {username.charAt(0)}
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1 text-gray-400 hover:text-red-500 transition-colors"
              title="로그아웃"
            >
              <PiSignOutBold size={18} />
            </button>
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
