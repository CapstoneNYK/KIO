import { useEffect, useState } from "react";
import { PiMagnifyingGlassBold, PiDownloadSimpleBold, PiCaretRightBold, PiCaretDownBold } from "react-icons/pi";
import { apiFetch } from "../api";

interface OrderItem {
  menu_name: string;
  temperature: string;
  quantity: number;
  unit_price: number;
  is_free: number;
}

interface Order {
  id: number;
  created_at: string;
  payment_method: string;
  total_amount: number;
  discount_amount: number;
  final_amount: number;
  is_packaging: number;
  items: OrderItem[];
}

const PAGE_SIZE = 50;
const GRID_COLUMNS = "150px 1fr 120px 110px 100px";

const formatDateTime = (s: string) => `${s.slice(5, 7)}.${s.slice(8, 10)} ${s.slice(11, 19)}`;

const toDateStr = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const menuSummary = (items: OrderItem[]) => {
  if (items.length === 0) return "—";
  const first = items[0].menu_name;
  return items.length > 1 ? `${first} 외 ${items.length - 1}건` : first;
};

const csvCell = (value: string | number) => {
  let text = String(value);
  if (typeof value === "string" && /^[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
};

const downloadCsv = (orders: Order[]) => {
  const header = ["주문번호", "주문시각", "결제수단", "구분", "메뉴", "주문금액", "할인금액", "결제금액"];
  const rows = orders.map((o) => [
    o.id,
    o.created_at,
    o.payment_method,
    o.is_packaging ? "포장" : "매장",
    o.items
      .map((i) => `${i.menu_name}${i.temperature ? `(${i.temperature})` : ""} x${i.quantity}${i.is_free ? " [무료]" : ""}`)
      .join(" / "),
    o.total_amount,
    o.discount_amount,
    o.final_amount,
  ]);
  const csv = "﻿" + [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `orders_${toDateStr(new Date()).replace(/-/g, "")}.csv`;
  link.click();
  URL.revokeObjectURL(url);
};

export const OrderHistory = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    const load = () => {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", `${dateFrom} 00:00:00`);
      if (dateTo) params.set("date_to", `${dateTo} 23:59:59`);
      const query = params.toString();
      apiFetch<Order[]>(`/api/admin/orders${query ? `?${query}` : ""}`)
        .then((data) => {
          setOrders(data);
          setError("");
        })
        .catch(() => setError("주문 내역을 불러오지 못했습니다."))
        .finally(() => setLoading(false));
    };
    setLoading(true);
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [dateFrom, dateTo]);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [search, dateFrom, dateTo]);

  const applyPreset = (from: string, to: string) => {
    setDateFrom(from);
    setDateTo(to);
  };

  const today = new Date();
  const presets: { label: string; from: string; to: string }[] = [
    { label: "전체", from: "", to: "" },
    { label: "오늘", from: toDateStr(today), to: toDateStr(today) },
    {
      label: "최근 7일",
      from: toDateStr(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6)),
      to: toDateStr(today),
    },
    {
      label: "이번 달",
      from: toDateStr(new Date(today.getFullYear(), today.getMonth(), 1)),
      to: toDateStr(today),
    },
  ];

  const keyword = search.trim();
  const filtered = orders.filter(
    (o) =>
      keyword === "" ||
      o.items.some((i) => i.menu_name.includes(keyword)) ||
      String(o.id).includes(keyword) ||
      o.payment_method.includes(keyword)
  );
  const visible = filtered.slice(0, visibleCount);

  const totalRevenue = filtered.reduce((s, o) => s + o.final_amount, 0);
  const totalDiscount = filtered.reduce((s, o) => s + o.discount_amount, 0);
  const couponCount = filtered.filter((o) => o.discount_amount > 0).length;

  return (
    <div className="flex flex-col gap-5">
      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: "총 주문", value: `${filtered.length}건` },
          { label: "쿠폰 할인 사용", value: `${couponCount}건` },
          { label: "총 할인 금액", value: `-₩${totalDiscount.toLocaleString()}` },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center justify-between">
            <span className="text-sm text-gray-500">{s.label}</span>
            <span className="text-base font-black text-gray-800">{s.value}</span>
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm font-semibold rounded-lg px-4 py-2.5">{error}</div>
      )}

      {/* Table card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {/* Date filter */}
        <div className="px-5 py-3 border-b border-gray-100 flex flex-wrap items-center gap-2">
          {presets.map((p) => {
            const active = dateFrom === p.from && dateTo === p.to;
            return (
              <button
                key={p.label}
                onClick={() => applyPreset(p.from, p.to)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors"
                style={{
                  backgroundColor: active ? "#F5A623" : "white",
                  color: active ? "white" : "#6B7280",
                  borderColor: active ? "#F5A623" : "#E5E7EB",
                }}
              >
                {p.label}
              </button>
            );
          })}
          <div className="flex items-center gap-1.5 ml-auto">
            <input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => setDateFrom(e.target.value)}
              className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 outline-none focus:border-amber-400"
              aria-label="시작일"
            />
            <span className="text-xs text-gray-400">~</span>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => setDateTo(e.target.value)}
              className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 outline-none focus:border-amber-400"
              aria-label="종료일"
            />
          </div>
        </div>

        {/* Search bar */}
        <div className="px-5 py-4 border-b border-gray-100 flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[220px] flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2">
            <PiMagnifyingGlassBold size={14} className="text-gray-400 shrink-0" />
            <input
              type="text"
              placeholder="메뉴명, 주문번호, 결제수단으로 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 text-sm text-gray-700 outline-none placeholder:text-gray-400"
            />
          </div>
          <button
            onClick={() => downloadCsv(filtered)}
            disabled={filtered.length === 0}
            className="flex items-center gap-2 border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <PiDownloadSimpleBold size={14} />
            내보내기
          </button>
          <span className="text-xs text-gray-400 shrink-0">총 {filtered.length}건 | 매출 ₩{totalRevenue.toLocaleString()}</span>
        </div>

        {/* Table (가로 스크롤) */}
        <div className="overflow-x-auto">
          <div className="min-w-[640px]">
            {/* Table header */}
            <div className="grid bg-gray-50 border-b border-gray-100 px-5 py-3" style={{ gridTemplateColumns: GRID_COLUMNS }}>
              {["주문시각", "메뉴", "결제수단", "할인 금액", "결제 금액"].map((h) => (
                <span key={h} className="text-xs font-bold text-gray-500">{h}</span>
              ))}
            </div>

            {loading && (
              <div className="py-16 text-center text-gray-400 text-sm">불러오는 중...</div>
            )}

            {/* Table rows */}
            {!loading && visible.map((order) => {
              const expanded = expandedId === order.id;
              return (
                <div key={order.id} className="border-b border-gray-50 last:border-0">
                  <button
                    onClick={() => setExpandedId(expanded ? null : order.id)}
                    className="grid w-full px-5 py-3.5 items-center text-left hover:bg-gray-50 transition-colors"
                    style={{ gridTemplateColumns: GRID_COLUMNS }}
                    aria-expanded={expanded}
                  >
                    <span className="flex items-center gap-1.5 text-sm text-gray-500 tabular-nums">
                      {expanded ? <PiCaretDownBold size={11} className="text-gray-400" /> : <PiCaretRightBold size={11} className="text-gray-400" />}
                      {formatDateTime(order.created_at)}
                    </span>
                    <span className="text-sm font-medium text-gray-800 pr-4 truncate">{menuSummary(order.items)}</span>
                    <span className="text-sm text-gray-500">{order.payment_method}</span>
                    <span className="text-sm font-semibold" style={{ color: order.discount_amount > 0 ? "#16A34A" : "#D1D5DB" }}>
                      {order.discount_amount > 0 ? `-₩${order.discount_amount.toLocaleString()}` : "—"}
                    </span>
                    <span className="text-sm font-bold text-gray-800 tabular-nums">₩{order.final_amount.toLocaleString()}</span>
                  </button>

                  {expanded && (
                    <div className="bg-gray-50/70 px-5 py-4 border-t border-gray-100">
                      <p className="text-xs font-bold text-gray-500 mb-3">
                        주문번호 #{order.id} · {order.is_packaging ? "포장" : "매장"}
                      </p>
                      <div className="flex flex-col gap-2">
                        {order.items.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm">
                            {item.temperature && (
                              <span
                                className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                                style={{
                                  backgroundColor: item.temperature === "HOT" ? "#FEF3C6" : "#DBEAFE",
                                  color: item.temperature === "HOT" ? "#D97706" : "#1D4ED8",
                                }}
                              >
                                {item.temperature}
                              </span>
                            )}
                            <span className="font-medium text-gray-800">{item.menu_name}</span>
                            <span className="text-gray-400">× {item.quantity}</span>
                            {item.is_free ? (
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-green-50 text-green-600">무료(쿠폰)</span>
                            ) : null}
                            <span className="ml-auto tabular-nums text-gray-600">
                              ₩{(item.is_free ? 0 : item.unit_price * item.quantity).toLocaleString()}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap justify-end gap-x-6 gap-y-1 text-xs text-gray-500">
                        <span>주문 금액 ₩{order.total_amount.toLocaleString()}</span>
                        <span>할인 -₩{order.discount_amount.toLocaleString()}</span>
                        <span className="font-bold text-gray-800">결제 ₩{order.final_amount.toLocaleString()}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {!loading && filtered.length === 0 && (
              <div className="py-16 text-center text-gray-400 text-sm">
                {orders.length === 0 ? "주문 내역이 없습니다." : "검색 결과가 없습니다."}
              </div>
            )}
          </div>
        </div>

        {!loading && filtered.length > visible.length && (
          <div className="border-t border-gray-100 p-3 flex justify-center">
            <button
              onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
              className="px-5 py-2 rounded-lg text-sm font-semibold text-gray-600 border border-gray-200 hover:bg-gray-50 transition-colors"
            >
              더 보기 ({filtered.length - visible.length}건 남음)
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
