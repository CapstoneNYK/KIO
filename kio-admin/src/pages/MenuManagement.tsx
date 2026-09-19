import { useEffect, useState } from "react";
import { FiEdit2, FiTrash2, FiUpload } from "react-icons/fi";
import { PiToggleRightFill, PiToggleLeftFill, PiPlusBold } from "react-icons/pi";
import { apiFetch, API, authHeaders } from "../api";

const CATEGORIES = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티"];

interface Menu {
  id: number;
  name: string;
  price: number;
  category: string;
  temps: string[];
  sold_out: boolean;
}

export const MenuManagement = () => {
  const [activeCategory, setActiveCategory] = useState("전체");
  const [menus, setMenus] = useState<Menu[]>([]);
  const [loading, setLoading] = useState(true);
  const [newMenu, setNewMenu] = useState({ name: "", price: "", category: "커피", temps: [] as string[] });

  useEffect(() => {
    const load = () => {
      apiFetch<Menu[]>("/api/admin/menus")
        .then(setMenus)
        .finally(() => setLoading(false));
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const filtered = activeCategory === "전체" ? menus : menus.filter((m) => m.category === activeCategory);
  const soldOutCount = menus.filter((m) => m.sold_out).length;

  const handleToggleSoldOut = async (id: number, current: boolean) => {
    const updated = await apiFetch<Menu>(`/api/admin/menus/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sold_out: !current }),
    });
    setMenus((prev) => prev.map((m) => m.id === id ? updated : m));
  };

  const handleDelete = async (id: number) => {
    await fetch(`${API}/api/admin/menus/${id}`, { method: "DELETE", headers: authHeaders() });
    setMenus((prev) => prev.filter((m) => m.id !== id));
  };

  const toggleTemp = (temp: string) => setNewMenu((prev) => ({
    ...prev,
    temps: prev.temps.includes(temp) ? prev.temps.filter((t) => t !== temp) : [...prev.temps, temp],
  }));

  const handleSave = async () => {
    if (!newMenu.name.trim() || !newMenu.price) return;
    const created = await apiFetch<Menu>("/api/admin/menus", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newMenu.name.trim(), price: parseInt(newMenu.price), category: newMenu.category, temps: newMenu.temps }),
    });
    setMenus((prev) => [...prev, created]);
    setNewMenu({ name: "", price: "", category: "커피", temps: [] });
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Add menu section — 상단 */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <p className="text-sm font-bold text-gray-700 flex items-center gap-1.5 mb-4">
          <PiPlusBold size={14} style={{ color: "#F5A623" }} />
          메뉴 추가
        </p>
        <div className="flex gap-4 items-end">
          <div className="flex flex-col gap-1.5 flex-1">
            <label className="text-xs font-semibold text-gray-500">메뉴명</label>
            <input type="text" placeholder="메뉴명 입력" value={newMenu.name}
              onChange={(e) => setNewMenu((p) => ({ ...p, name: e.target.value }))}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
          </div>
          <div className="flex flex-col gap-1.5 w-40">
            <label className="text-xs font-semibold text-gray-500">가격 (원)</label>
            <input type="number" placeholder="0" value={newMenu.price}
              onChange={(e) => setNewMenu((p) => ({ ...p, price: e.target.value }))}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">카테고리</label>
            <div className="flex gap-1.5">
              {CATEGORIES.filter((c) => c !== "전체").map((cat) => (
                <button key={cat} onClick={() => setNewMenu((p) => ({ ...p, category: cat }))}
                  className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors"
                  style={{ backgroundColor: newMenu.category === cat ? "#F5A623" : "white", color: newMenu.category === cat ? "white" : "#6B7280", borderColor: newMenu.category === cat ? "#F5A623" : "#E5E7EB" }}>
                  {cat}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">온도</label>
            <div className="flex gap-2">
              {["HOT", "ICE"].map((temp) => (
                <button key={temp} onClick={() => toggleTemp(temp)}
                  className="px-5 py-1.5 rounded-lg text-xs font-bold border transition-colors"
                  style={{
                    backgroundColor: newMenu.temps.includes(temp) ? (temp === "HOT" ? "#FEF3C6" : "#DBEAFE") : "white",
                    color: newMenu.temps.includes(temp) ? (temp === "HOT" ? "#D97706" : "#1D4ED8") : "#9CA3AF",
                    borderColor: newMenu.temps.includes(temp) ? (temp === "HOT" ? "#FCD34D" : "#93C5FD") : "#E5E7EB",
                  }}>
                  {temp}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">이미지</label>
            <div className="border border-dashed border-gray-200 rounded-lg px-4 py-2 flex items-center gap-2 cursor-pointer hover:bg-gray-50 transition-colors">
              <FiUpload size={13} className="text-gray-400" />
              <span className="text-xs text-gray-400">업로드</span>
            </div>
          </div>
          <button onClick={handleSave}
            className="px-8 py-2 rounded-lg font-bold text-sm text-white transition-colors hover:brightness-95 shrink-0"
            style={{ backgroundColor: "#F5A623" }}>
            저장
          </button>
        </div>
      </div>

      {/* Filter row */}
      <div className="flex items-center gap-4">
        <div className="flex gap-2">
          {CATEGORIES.map((cat) => (
            <button key={cat} onClick={() => setActiveCategory(cat)}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-colors border"
              style={{ backgroundColor: activeCategory === cat ? "#F5A623" : "white", color: activeCategory === cat ? "white" : "#6B7280", borderColor: activeCategory === cat ? "#F5A623" : "#E5E7EB" }}>
              {cat}
            </button>
          ))}
        </div>
        <span className="text-sm text-gray-400">
          {filtered.length}종
          {soldOutCount > 0 && <span className="ml-2 text-red-400 font-semibold">품절 {soldOutCount}종</span>}
        </span>
      </div>

      {/* Menu grid */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">불러오는 중...</div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {filtered.map((menu) => (
            <div key={menu.id}
              className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden"
              style={{ opacity: menu.sold_out ? 0.65 : 1 }}>
              <div className="h-32 relative flex items-center justify-center" style={{ backgroundColor: menu.sold_out ? "#F3F4F6" : "#FFFBEB" }}>
                {menu.sold_out && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="bg-gray-500 text-white text-xs font-bold px-3 py-1 rounded-full">품절</span>
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="font-bold text-gray-800 text-sm mb-0.5">{menu.name}</p>
                <p className="text-sm font-black mb-2" style={{ color: "#F5A623" }}>₩{menu.price.toLocaleString()}</p>
                <div className="flex items-center justify-between">
                  <div className="flex gap-1">
                    {menu.temps.map((t) => (
                      <span key={t} className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                        style={{ backgroundColor: t === "HOT" ? "#FEF3C6" : "#DBEAFE", color: t === "HOT" ? "#D97706" : "#1D4ED8" }}>
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleToggleSoldOut(menu.id, menu.sold_out)} className="hover:opacity-75 transition-opacity">
                      {menu.sold_out
                        ? <PiToggleLeftFill size={22} className="text-gray-400" />
                        : <PiToggleRightFill size={22} style={{ color: "#F5A623" }} />}
                    </button>
                    <button className="p-1 text-gray-400 hover:text-amber-500 transition-colors"><FiEdit2 size={13} /></button>
                    <button onClick={() => handleDelete(menu.id)} className="p-1 text-gray-400 hover:text-red-500 transition-colors"><FiTrash2 size={13} /></button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
