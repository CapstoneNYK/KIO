import { useEffect, useRef, useState } from "react";
import { FiEdit2, FiTrash2, FiUpload, FiX } from "react-icons/fi";
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
  image_url: string | null;
}

const imageSrc = (imageUrl: string | null) => (imageUrl ? `${API}${imageUrl}` : null);

export const MenuManagement = () => {
  const [activeCategory, setActiveCategory] = useState("전체");
  const [menus, setMenus] = useState<Menu[]>([]);
  const [loading, setLoading] = useState(true);
  const [newMenu, setNewMenu] = useState({
    name: "",
    price: "",
    category: "커피",
    temps: [] as string[],
    imageUrl: null as string | null,
  });
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [actionError, setActionError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    name: "",
    price: "",
    category: "커피",
    temps: [] as string[],
    imageUrl: null as string | null,
  });
  const [editUploading, setEditUploading] = useState(false);
  const [editError, setEditError] = useState("");
  const editFileInputRef = useRef<HTMLInputElement>(null);

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
    setActionError("");
    try {
      const updated = await apiFetch<Menu>(`/api/admin/menus/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sold_out: !current }),
      });
      setMenus((prev) => prev.map((m) => m.id === id ? updated : m));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "품절 상태를 변경하지 못했습니다.");
    }
  };

  const handleDelete = async (menu: Menu) => {
    if (!window.confirm(`'${menu.name}' 메뉴를 삭제할까요?\n삭제하면 되돌릴 수 없습니다.`)) return;
    setActionError("");
    try {
      await apiFetch<void>(`/api/admin/menus/${menu.id}`, { method: "DELETE" });
      setMenus((prev) => prev.filter((m) => m.id !== menu.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "메뉴를 삭제하지 못했습니다.");
    }
  };

  const toggleTemp = (temp: string) => setNewMenu((prev) => ({
    ...prev,
    temps: prev.temps.includes(temp) ? prev.temps.filter((t) => t !== temp) : [...prev.temps, temp],
  }));

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    setUploadError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API}/api/admin/uploads/menu-image`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? "이미지 업로드에 실패했습니다.");
      }
      const data: { image_url: string } = await res.json();
      setNewMenu((p) => ({ ...p, imageUrl: data.image_url }));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "이미지 업로드에 실패했습니다.");
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    if (!newMenu.name.trim() || newMenu.price === "") {
      setUploadError("메뉴명과 가격을 입력해주세요.");
      return;
    }
    const price = parseInt(newMenu.price);
    if (Number.isNaN(price) || price < 0) {
      setUploadError("가격은 0원 이상의 숫자로 입력해주세요.");
      return;
    }
    setUploadError("");
    try {
      const created = await apiFetch<Menu>("/api/admin/menus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newMenu.name.trim(),
          price,
          category: newMenu.category,
          temps: newMenu.temps,
          image_url: newMenu.imageUrl,
        }),
      });
      setMenus((prev) => [...prev, created]);
      setNewMenu({ name: "", price: "", category: "커피", temps: [], imageUrl: null });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "메뉴를 추가하지 못했습니다.");
    }
  };

  const openEdit = (menu: Menu) => {
    setEditingId(menu.id);
    setEditForm({
      name: menu.name,
      price: String(menu.price),
      category: menu.category,
      temps: menu.temps,
      imageUrl: menu.image_url,
    });
    setEditError("");
  };

  const toggleEditTemp = (temp: string) => setEditForm((prev) => ({
    ...prev,
    temps: prev.temps.includes(temp) ? prev.temps.filter((t) => t !== temp) : [...prev.temps, temp],
  }));

  const handleEditImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setEditUploading(true);
    setEditError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API}/api/admin/uploads/menu-image`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? "이미지 업로드에 실패했습니다.");
      }
      const data: { image_url: string } = await res.json();
      setEditForm((p) => ({ ...p, imageUrl: data.image_url }));
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "이미지 업로드에 실패했습니다.");
    } finally {
      setEditUploading(false);
    }
  };

  const handleEditSave = async () => {
    if (editingId == null) return;
    if (!editForm.name.trim() || editForm.price === "") {
      setEditError("메뉴명과 가격을 입력해주세요.");
      return;
    }
    const price = parseInt(editForm.price);
    if (Number.isNaN(price) || price < 0) {
      setEditError("가격은 0원 이상의 숫자로 입력해주세요.");
      return;
    }
    setEditError("");
    try {
      const updated = await apiFetch<Menu>(`/api/admin/menus/${editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editForm.name.trim(),
          price,
          category: editForm.category,
          temps: editForm.temps,
          image_url: editForm.imageUrl,
        }),
      });
      setMenus((prev) => prev.map((m) => m.id === editingId ? updated : m));
      setEditingId(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "메뉴를 수정하지 못했습니다.");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Add menu section — 상단 */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <p className="text-sm font-bold text-gray-700 flex items-center gap-1.5 mb-4">
          <PiPlusBold size={14} style={{ color: "#F5A623" }} />
          메뉴 추가
        </p>
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(160px,320px)_110px_182px_max-content_max-content_max-content] gap-4 items-start">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">메뉴명</label>
            <input type="text" placeholder="메뉴명 입력" value={newMenu.name}
              onChange={(e) => setNewMenu((p) => ({ ...p, name: e.target.value }))}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">가격 (원)</label>
            <input type="number" placeholder="0" value={newMenu.price}
              onChange={(e) => setNewMenu((p) => ({ ...p, price: e.target.value }))}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">카테고리</label>
            <div className="flex flex-wrap gap-1.5">
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
            <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif"
              onChange={handleImageSelect} className="hidden" />
            {newMenu.imageUrl ? (
              <div className="relative w-11 h-11">
                <img src={imageSrc(newMenu.imageUrl) ?? undefined} alt="미리보기"
                  className="w-11 h-11 rounded-lg object-cover border border-gray-200" />
                <button onClick={() => setNewMenu((p) => ({ ...p, imageUrl: null }))}
                  className="absolute -top-1.5 -right-1.5 bg-gray-600 text-white rounded-full p-0.5 hover:bg-red-500 transition-colors">
                  <FiX size={10} />
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading}
                className="w-11 h-11 border border-dashed border-gray-300 rounded-lg flex items-center justify-center hover:bg-gray-50 transition-colors disabled:opacity-50">
                <FiUpload size={15} className="text-gray-400" />
              </button>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 invisible">저장</label>
            <button onClick={handleSave}
              className="px-8 py-2 rounded-lg font-bold text-sm text-white transition-colors hover:brightness-95 shrink-0"
              style={{ backgroundColor: "#F5A623" }}>
              저장
            </button>
          </div>
        </div>
        {uploading && <p className="text-xs text-gray-400 mt-2">이미지 업로드 중...</p>}
        {uploadError && <p className="text-xs font-semibold text-red-500 mt-2">{uploadError}</p>}
      </div>

      {actionError && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm font-semibold rounded-lg px-4 py-2.5 flex items-center justify-between gap-3">
          <span>{actionError}</span>
          <button onClick={() => setActionError("")} className="text-red-400 hover:text-red-600 shrink-0" aria-label="닫기">
            <FiX size={14} />
          </button>
        </div>
      )}

      {/* Filter row */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex flex-wrap gap-2">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((menu) => (
            <div key={menu.id}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-4"
              style={{ opacity: menu.sold_out ? 0.6 : 1 }}>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <p className="font-bold text-gray-800 text-sm">{menu.name}</p>
                  {menu.sold_out && (
                    <span className="bg-gray-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0">품절</span>
                  )}
                </div>
                <span className="text-[11px] font-semibold text-gray-400 shrink-0">{menu.category}</span>
              </div>
              <p className="text-base font-black mb-3" style={{ color: "#F5A623" }}>₩{menu.price.toLocaleString()}</p>
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
                  <button onClick={() => openEdit(menu)} className="p-1 text-gray-400 hover:text-amber-500 transition-colors"><FiEdit2 size={13} /></button>
                  <button onClick={() => handleDelete(menu)} className="p-1 text-gray-400 hover:text-red-500 transition-colors"><FiTrash2 size={13} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit modal */}
      {editingId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setEditingId(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <p className="text-sm font-bold text-gray-700 mb-4">메뉴 수정</p>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">메뉴명</label>
                <input type="text" value={editForm.name}
                  onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">가격 (원)</label>
                <input type="number" value={editForm.price}
                  onChange={(e) => setEditForm((p) => ({ ...p, price: e.target.value }))}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">카테고리</label>
                <div className="flex flex-wrap gap-1.5">
                  {CATEGORIES.filter((c) => c !== "전체").map((cat) => (
                    <button key={cat} onClick={() => setEditForm((p) => ({ ...p, category: cat }))}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors"
                      style={{ backgroundColor: editForm.category === cat ? "#F5A623" : "white", color: editForm.category === cat ? "white" : "#6B7280", borderColor: editForm.category === cat ? "#F5A623" : "#E5E7EB" }}>
                      {cat}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">온도</label>
                <div className="flex gap-2">
                  {["HOT", "ICE"].map((temp) => (
                    <button key={temp} onClick={() => toggleEditTemp(temp)}
                      className="px-5 py-1.5 rounded-lg text-xs font-bold border transition-colors"
                      style={{
                        backgroundColor: editForm.temps.includes(temp) ? (temp === "HOT" ? "#FEF3C6" : "#DBEAFE") : "white",
                        color: editForm.temps.includes(temp) ? (temp === "HOT" ? "#D97706" : "#1D4ED8") : "#9CA3AF",
                        borderColor: editForm.temps.includes(temp) ? (temp === "HOT" ? "#FCD34D" : "#93C5FD") : "#E5E7EB",
                      }}>
                      {temp}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">이미지</label>
                <input ref={editFileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif"
                  onChange={handleEditImageSelect} className="hidden" />
                <div className="flex items-center gap-3">
                  {editForm.imageUrl ? (
                    <img src={imageSrc(editForm.imageUrl) ?? undefined} alt="미리보기"
                      className="w-11 h-11 rounded-lg object-cover border border-gray-200" />
                  ) : (
                    <div className="w-11 h-11 rounded-lg bg-gray-50 border border-gray-100" />
                  )}
                  <button type="button" onClick={() => editFileInputRef.current?.click()} disabled={editUploading}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50">
                    {editUploading ? "업로드 중..." : "이미지 변경"}
                  </button>
                </div>
              </div>
              {editError && <p className="text-xs font-semibold text-red-500">{editError}</p>}
              <div className="flex gap-2 mt-2">
                <button onClick={() => setEditingId(null)}
                  className="flex-1 py-2 rounded-lg font-bold text-sm text-gray-600 border border-gray-200 hover:bg-gray-50 transition-colors">
                  취소
                </button>
                <button onClick={handleEditSave}
                  className="flex-1 py-2 rounded-lg font-bold text-sm text-white transition-colors hover:brightness-95"
                  style={{ backgroundColor: "#F5A623" }}>
                  저장
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
