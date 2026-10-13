import { useEffect, useRef, useState } from "react";
import { FiEdit2, FiTrash2, FiUpload, FiX } from "react-icons/fi";
import { PiToggleRightFill, PiToggleLeftFill, PiPlusBold, PiTicketBold } from "react-icons/pi";
import { apiFetch, API, authHeaders } from "../api";

// 결제 모달(PaymentModal.tsx)에 이미 버튼/아이콘으로 있는 할인수단만 선택 가능.
// 새 결제수단 자체를 추가하려면 프론트에 버튼을 먼저 만들어야 한다.
const METHOD_LABELS: Record<string, string> = {
  kt: "KT VIP",
  tmembership: "T멤버십",
  uzu: "T우주",
  cjone: "CJ ONE",
};
const METHOD_CODES = Object.keys(METHOD_LABELS);

interface Discount {
  id: number;
  name: string;
  method_code: string;
  description: string;
  active: boolean;
  image_url: string | null;
}

const imageSrc = (imageUrl: string | null) => (imageUrl ? `${API}${imageUrl}` : null);

const emptyForm = { name: "", method_code: "kt", description: "", active: true, imageUrl: null as string | null };

export const DiscountManagement = () => {
  const [discounts, setDiscounts] = useState<Discount[]>([]);
  const [loading, setLoading] = useState(true);
  const [newDiscount, setNewDiscount] = useState(emptyForm);
  const [saveError, setSaveError] = useState("");
  const [actionError, setActionError] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState(emptyForm);
  const [editError, setEditError] = useState("");
  const [editUploading, setEditUploading] = useState(false);
  const editFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const load = () => {
      apiFetch<Discount[]>("/api/admin/discounts")
        .then(setDiscounts)
        .finally(() => setLoading(false));
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const uploadImage = async (file: File): Promise<string> => {
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
    return data.image_url;
  };

  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    setSaveError("");
    try {
      const image_url = await uploadImage(file);
      setNewDiscount((p) => ({ ...p, imageUrl: image_url }));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "이미지 업로드에 실패했습니다.");
    } finally {
      setUploading(false);
    }
  };

  const handleEditImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setEditUploading(true);
    setEditError("");
    try {
      const image_url = await uploadImage(file);
      setEditForm((p) => ({ ...p, imageUrl: image_url }));
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "이미지 업로드에 실패했습니다.");
    } finally {
      setEditUploading(false);
    }
  };

  const handleToggleActive = async (id: number, current: boolean) => {
    setActionError("");
    try {
      const updated = await apiFetch<Discount>(`/api/admin/discounts/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !current }),
      });
      setDiscounts((prev) => prev.map((d) => d.id === id ? updated : d));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "상태를 변경하지 못했습니다.");
    }
  };

  const handleDelete = async (discount: Discount) => {
    if (!window.confirm(`'${discount.name}' 할인을 삭제할까요?\n삭제하면 되돌릴 수 없습니다.`)) return;
    setActionError("");
    try {
      await apiFetch<void>(`/api/admin/discounts/${discount.id}`, { method: "DELETE" });
      setDiscounts((prev) => prev.filter((d) => d.id !== discount.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "삭제하지 못했습니다.");
    }
  };

  const handleSave = async () => {
    if (!newDiscount.name.trim()) {
      setSaveError("할인 이름을 입력해주세요.");
      return;
    }
    setSaveError("");
    try {
      const created = await apiFetch<Discount>("/api/admin/discounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newDiscount.name.trim(),
          method_code: newDiscount.method_code,
          description: newDiscount.description,
          active: newDiscount.active,
          image_url: newDiscount.imageUrl,
        }),
      });
      setDiscounts((prev) => [...prev, created]);
      setNewDiscount(emptyForm);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "할인 혜택을 추가하지 못했습니다.");
    }
  };

  const openEdit = (discount: Discount) => {
    setEditingId(discount.id);
    setEditForm({
      name: discount.name,
      method_code: discount.method_code,
      description: discount.description,
      active: discount.active,
      imageUrl: discount.image_url,
    });
    setEditError("");
  };

  const handleEditSave = async () => {
    if (editingId == null) return;
    if (!editForm.name.trim()) {
      setEditError("할인 이름을 입력해주세요.");
      return;
    }
    setEditError("");
    try {
      const updated = await apiFetch<Discount>(`/api/admin/discounts/${editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editForm.name.trim(),
          method_code: editForm.method_code,
          description: editForm.description,
          active: editForm.active,
          image_url: editForm.imageUrl,
        }),
      });
      setDiscounts((prev) => prev.map((d) => d.id === editingId ? updated : d));
      setEditingId(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "수정하지 못했습니다.");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Add discount section */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <p className="text-sm font-bold text-gray-700 flex items-center gap-1.5 mb-4">
          <PiPlusBold size={14} style={{ color: "#F5A623" }} />
          할인 혜택 추가
        </p>
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px_64px] gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-gray-500">이름</label>
              <input type="text" placeholder="예: T멤버십 T Day" value={newDiscount.name}
                onChange={(e) => setNewDiscount((p) => ({ ...p, name: e.target.value }))}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-gray-500">대상 결제수단</label>
              <div className="flex flex-wrap gap-1.5">
                {METHOD_CODES.map((code) => (
                  <button key={code} onClick={() => setNewDiscount((p) => ({ ...p, method_code: code }))}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors"
                    style={{ backgroundColor: newDiscount.method_code === code ? "#F5A623" : "white", color: newDiscount.method_code === code ? "white" : "#6B7280", borderColor: newDiscount.method_code === code ? "#F5A623" : "#E5E7EB" }}>
                    {METHOD_LABELS[code]}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-gray-500">포스터</label>
              <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif"
                onChange={handleImageSelect} className="hidden" />
              {newDiscount.imageUrl ? (
                <div className="relative w-11 h-11">
                  <img src={imageSrc(newDiscount.imageUrl) ?? undefined} alt="미리보기"
                    className="w-11 h-11 rounded-lg object-cover border border-gray-200" />
                  <button onClick={() => setNewDiscount((p) => ({ ...p, imageUrl: null }))}
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
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500">안내 문구 (줄바꿈으로 항목 구분)</label>
            <textarea placeholder="예: 바코드 스캔 시 음료 1종 50% 할인" value={newDiscount.description} rows={3}
              onChange={(e) => setNewDiscount((p) => ({ ...p, description: e.target.value }))}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors resize-y" />
          </div>
          <p className="text-[11px] text-gray-400 -mt-2">포스터를 올리면 키오스크 첫 화면 배너에 노출됩니다. 비워두면 배너에는 안 뜨고 AI 안내에만 쓰여요.</p>
          <button onClick={handleSave}
            className="self-start px-8 py-2 rounded-lg font-bold text-sm text-white transition-colors hover:brightness-95"
            style={{ backgroundColor: "#F5A623" }}>
            저장
          </button>
        </div>
        {uploading && <p className="text-xs text-gray-400 mt-2">이미지 업로드 중...</p>}
        {saveError && <p className="text-xs font-semibold text-red-500 mt-2">{saveError}</p>}
      </div>

      {actionError && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm font-semibold rounded-lg px-4 py-2.5 flex items-center justify-between gap-3">
          <span>{actionError}</span>
          <button onClick={() => setActionError("")} className="text-red-400 hover:text-red-600 shrink-0" aria-label="닫기">
            <FiX size={14} />
          </button>
        </div>
      )}

      {/* Discount list */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">불러오는 중...</div>
      ) : discounts.length === 0 ? (
        <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100 flex flex-col items-center justify-center gap-2 text-gray-400">
          <PiTicketBold size={24} />
          <p className="text-sm">등록된 할인 혜택이 없습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {discounts.map((discount) => (
            <div key={discount.id}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex flex-col"
              style={{ opacity: discount.active ? 1 : 0.6 }}>
              <div className="flex items-start gap-3 mb-2">
                {imageSrc(discount.image_url) ? (
                  <img src={imageSrc(discount.image_url) ?? undefined} alt={discount.name}
                    className="w-11 h-14 rounded-lg object-cover border border-gray-100 shrink-0" />
                ) : (
                  <div className="w-11 h-14 rounded-lg bg-gray-50 border border-gray-100 shrink-0 flex items-center justify-center">
                    <PiTicketBold size={16} className="text-gray-300" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-gray-800 text-sm">{discount.name}</p>
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                      style={{ backgroundColor: "#FFF3DC", color: "#D97706" }}>
                      {METHOD_LABELS[discount.method_code] ?? discount.method_code}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 whitespace-pre-line mt-1">
                    {discount.description || "안내 문구가 없습니다."}
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between pt-2 mt-auto border-t border-gray-50">
                <span className="text-[11px] font-semibold" style={{ color: discount.active ? "#22C55E" : "#9CA3AF" }}>
                  {discount.active ? "노출 중" : "비노출"}
                </span>
                <div className="flex items-center gap-1">
                  <button onClick={() => handleToggleActive(discount.id, discount.active)} className="hover:opacity-75 transition-opacity">
                    {discount.active
                      ? <PiToggleRightFill size={22} style={{ color: "#F5A623" }} />
                      : <PiToggleLeftFill size={22} className="text-gray-400" />}
                  </button>
                  <button onClick={() => openEdit(discount)} className="p-1 text-gray-400 hover:text-amber-500 transition-colors"><FiEdit2 size={13} /></button>
                  <button onClick={() => handleDelete(discount)} className="p-1 text-gray-400 hover:text-red-500 transition-colors"><FiTrash2 size={13} /></button>
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
            <p className="text-sm font-bold text-gray-700 mb-4">할인 혜택 수정</p>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">이름</label>
                <input type="text" value={editForm.name}
                  onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">대상 결제수단</label>
                <div className="flex flex-wrap gap-1.5">
                  {METHOD_CODES.map((code) => (
                    <button key={code} onClick={() => setEditForm((p) => ({ ...p, method_code: code }))}
                      className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors"
                      style={{ backgroundColor: editForm.method_code === code ? "#F5A623" : "white", color: editForm.method_code === code ? "white" : "#6B7280", borderColor: editForm.method_code === code ? "#F5A623" : "#E5E7EB" }}>
                      {METHOD_LABELS[code]}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">포스터</label>
                <input ref={editFileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif"
                  onChange={handleEditImageSelect} className="hidden" />
                <div className="flex items-center gap-3">
                  {editForm.imageUrl ? (
                    <img src={imageSrc(editForm.imageUrl) ?? undefined} alt="미리보기"
                      className="w-11 h-14 rounded-lg object-cover border border-gray-200" />
                  ) : (
                    <div className="w-11 h-14 rounded-lg bg-gray-50 border border-gray-100" />
                  )}
                  <div className="flex flex-col gap-1.5">
                    <button type="button" onClick={() => editFileInputRef.current?.click()} disabled={editUploading}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50">
                      {editUploading ? "업로드 중..." : "이미지 변경"}
                    </button>
                    {editForm.imageUrl && (
                      <button type="button" onClick={() => setEditForm((p) => ({ ...p, imageUrl: null }))}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-gray-200 text-gray-400 hover:bg-gray-50 hover:text-red-500 transition-colors">
                        이미지 제거
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500">안내 문구</label>
                <textarea value={editForm.description} rows={4}
                  onChange={(e) => setEditForm((p) => ({ ...p, description: e.target.value }))}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-amber-400 transition-colors resize-y" />
              </div>
              <label className="flex items-center gap-2 text-xs font-semibold text-gray-600 cursor-pointer">
                <input type="checkbox" checked={editForm.active}
                  onChange={(e) => setEditForm((p) => ({ ...p, active: e.target.checked }))} />
                노출 중 (끄면 AI 답변/힌트/배너에서 제외)
              </label>
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
