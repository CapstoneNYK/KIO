import { useEffect, useState } from "react";
import { PiMagnifyingGlassBold, PiDownloadSimpleBold } from "react-icons/pi";
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
  items: OrderItem[];
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

function menuSummary(items: OrderItem[]) {
  if (items.length === 0) return "—";
  const first = items[0].menu_name;
  return items.length > 1 ? `${first} 외 ${items.length - 1}건` : first;
}

export const OrderHistory = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = () => {
      apiFetch<Order[]>("/api/admin/orders")
        .then(setOrders)
        .finally(() => setLoading(false));
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const filtered = orders.filter(
    (o) =>
      search === "" ||
      menuSummary(o.items).includes(search) ||
      String(o.id).includes(search) ||
      o.payment_method.includes(search)
  );

  const totalRevenue = filtered.reduce((s, o) => s + o.final_amount, 0);
  const totalDiscount = filtered.reduce((s, o) => s + o.discount_amount, 0);
  const couponCount = filtered.filter((o) => o.discount_amount > 0).length;

  return (
    <div className="flex flex-col gap-5">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
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

      {/* Table card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {/* Search bar */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="flex-1 flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2">
            <PiMagnifyingGlassBold size={14} className="text-gray-400 shrink-0" />
            <input
              type="text"
              placeholder="메뉴명, 주문번호, 결제수단으로 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 text-sm text-gray-700 outline-none placeholder:text-gray-400"
            />
          </div>
          <button className="flex items-center gap-2 border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors">
            <PiDownloadSimpleBold size={14} />
            내보내기
          </button>
          <span className="text-xs text-gray-400">총 {filtered.length}건 | 매출 ₩{totalRevenue.toLocaleString()}</span>
        </div>

        {/* Table header */}
        <div className="grid bg-gray-50 border-b border-gray-100 px-5 py-3" style={{ gridTemplateColumns: "90px 1fr 120px 110px 90px" }}>
          {["주문시각", "메뉴", "결제수단", "할인 금액", "결제 금액"].map((h) => (
            <span key={h} className="text-xs font-bold text-gray-500">{h}</span>
          ))}
        </div>

        {/* Loading */}
        {loading && (
          <div className="py-16 text-center text-gray-400 text-sm">불러오는 중...</div>
        )}

        {/* Table rows */}
        {!loading && filtered.map((order) => (
          <div
            key={order.id}
            className="grid px-5 py-3.5 border-b border-gray-50 last:border-0 items-center hover:bg-gray-50 transition-colors"
            style={{ gridTemplateColumns: "90px 1fr 120px 110px 90px" }}
          >
            <span className="text-sm text-gray-500 tabular-nums">{formatTime(order.created_at)}</span>
            <span className="text-sm font-medium text-gray-800 pr-4 truncate">{menuSummary(order.items)}</span>
            <span className="text-sm text-gray-500">{order.payment_method}</span>
            <span className="text-sm font-semibold" style={{ color: order.discount_amount > 0 ? "#16A34A" : "#D1D5DB" }}>
              {order.discount_amount > 0 ? `-₩${order.discount_amount.toLocaleString()}` : "—"}
            </span>
            <span className="text-sm font-bold text-gray-800 tabular-nums">₩{order.final_amount.toLocaleString()}</span>
          </div>
        ))}

        {!loading && filtered.length === 0 && (
          <div className="py-16 text-center text-gray-400 text-sm">
            {orders.length === 0 ? "아직 주문 내역이 없습니다." : "검색 결과가 없습니다."}
          </div>
        )}
      </div>
    </div>
  );
};
