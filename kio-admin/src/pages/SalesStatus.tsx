import { useState, useEffect } from "react";
import { PiTrendUpBold, PiTrendDownBold } from "react-icons/pi";
import { apiFetch } from "../api";

type Period = "오늘" | "이번 주" | "이번 달";
const PERIOD_PARAM: Record<Period, string> = { "오늘": "today", "이번 주": "week", "이번 달": "month" };

interface SalesData {
  current: { sales: number; orders: number; avg: number; coupons: number };
  previous: { sales: number; orders: number; avg: number; coupons: number };
}

const pct = (curr: number, prev: number) =>
  prev === 0 ? "0.0" : (((curr - prev) / prev) * 100).toFixed(1);

const StatCard = ({ title, value, change, isPositive, sub }: {
  title: string; value: string; change: string; isPositive: boolean; sub?: string;
}) => (
  <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
    <p className="text-xs text-gray-500 font-medium mb-2">{title}</p>
    <p className="text-2xl font-black text-gray-900 mb-1">{value}</p>
    {sub && <p className="text-xs text-gray-400 mb-1">{sub}</p>}
    <div className="flex items-center gap-1 text-xs font-semibold" style={{ color: isPositive ? "#22C55E" : "#EF4444" }}>
      {isPositive ? <PiTrendUpBold size={12} /> : <PiTrendDownBold size={12} />}
      {change}% 전기 대비
    </div>
  </div>
);

export const SalesStatus = () => {
  const [period, setPeriod] = useState<Period>("오늘");
  const [data, setData] = useState<SalesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => {
      setLoading(true);
      apiFetch<SalesData>(`/api/admin/sales?period=${PERIOD_PARAM[period]}`)
        .then(setData)
        .finally(() => setLoading(false));
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [period]);

  const curr = data?.current;
  const prev = data?.previous;

  return (
    <div className="flex flex-col gap-6">
      {/* Period selector */}
      <div className="flex justify-end">
        <div className="flex rounded-lg overflow-hidden border border-gray-200 bg-white">
          {(["오늘", "이번 주", "이번 달"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className="w-20 py-2 text-sm font-semibold transition-colors"
              style={{
                backgroundColor: period === p ? "#F5A623" : "transparent",
                color: period === p ? "white" : "#6B7280",
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {loading || !curr || !prev ? (
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">불러오는 중...</div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-4">
            <StatCard title="총 매출액" value={`₩${curr.sales.toLocaleString()}`} change={pct(curr.sales, prev.sales)} isPositive={curr.sales >= prev.sales} />
            <StatCard title="총 주문 건수" value={`${curr.orders.toLocaleString()}건`} change={pct(curr.orders, prev.orders)} isPositive={curr.orders >= prev.orders} />
            <StatCard title="평균 주문 금액" value={`₩${curr.avg.toLocaleString()}`} change={pct(curr.avg, prev.avg)} isPositive={curr.avg >= prev.avg} />
            <StatCard
              title="쿠폰 사용"
              value={`${curr.coupons}건`}
              change={pct(curr.coupons, prev.coupons)}
              isPositive={curr.coupons >= prev.coupons}
              sub={curr.orders > 0 ? `전환율 ${((curr.coupons / curr.orders) * 100).toFixed(1)}%` : undefined}
            />
          </div>

          {/* 데이터 없음 안내 */}
          {curr.orders === 0 && (
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100 flex items-center justify-center">
              <p className="text-sm text-gray-400">해당 기간에 주문 데이터가 없습니다.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
};
