import type { PageId } from "../App";
import {
  PiChartBarBold,
  PiChartPieBold,
  PiClipboardTextBold,
  PiForkKnifeBold,
  PiStorefrontBold,
} from "react-icons/pi";

const NAV_ITEMS: { id: PageId; label: string; icon: React.ComponentType<{ size?: number }> }[] = [
  { id: "sales", label: "매출 현황", icon: PiChartBarBold },
  { id: "analytics", label: "메뉴 분석", icon: PiChartPieBold },
  { id: "orders", label: "주문 내역", icon: PiClipboardTextBold },
  { id: "menus", label: "메뉴 관리", icon: PiForkKnifeBold },
];

interface SidebarProps {
  activePage: PageId;
  onSelect: (page: PageId) => void;
  username: string;
  open: boolean;
  onClose: () => void;
}

export const Sidebar = ({ activePage, onSelect, username, open, onClose }: SidebarProps) => {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={onClose} />}
      <div
        className={`fixed inset-y-0 left-0 z-40 w-52 flex flex-col flex-shrink-0 bg-white border-r transition-transform lg:static lg:z-auto lg:h-full lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
        style={{ borderColor: "#FEE685" }}
      >
        {/* Logo */}
        <div className="px-5 border-b flex items-center" style={{ borderColor: "#FEE685", height: "68px" }}>
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center font-black text-[10px] text-white tracking-wider"
              style={{ backgroundColor: "#F5A623" }}
            >
              NYK
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm leading-tight">NYK CAFE</p>
              <p className="text-[10px] text-gray-400 leading-tight">관리자 페이지</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
            const isActive = activePage === id;
            return (
              <button
                key={id}
                onClick={() => onSelect(id)}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg w-full text-left transition-colors"
                style={{
                  backgroundColor: isActive ? "#FFF3DC" : "transparent",
                  color: isActive ? "#D97706" : "#9CA3AF",
                  borderLeft: `3px solid ${isActive ? "#F5A623" : "transparent"}`,
                }}
                onMouseEnter={(e) => {
                  if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = "#FFFBEB";
                }}
                onMouseLeave={(e) => {
                  if (!isActive) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
                }}
              >
                <Icon size={17} />
                <span className="text-sm font-semibold">{label}</span>
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="px-5 py-4 border-t" style={{ borderColor: "#FEE685" }}>
          <div className="flex items-center gap-2 min-w-0">
            <PiStorefrontBold size={15} className="text-gray-400 shrink-0" />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-gray-600 truncate">{username}</p>
              <p className="text-[10px] text-gray-400">NYK CAFE 1호점 · 관리자</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
