import { useState, useEffect } from "react";
import { PiTrendUpBold, PiTrendDownBold } from "react-icons/pi";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { apiFetch } from "../api";

type Period = "오늘" | "이번 주" | "이번 달";
const PERIOD_PARAM: Record<Period, string> = { "오늘": "today", "이번 주": "week", "이번 달": "month" };
const TREND_SUBTITLE: Record<Period, string> = { "오늘": "시간대별", "이번 주": "요일별", "이번 달": "일별" };

const BAR_COLOR = "#D97706";

interface SalesData {
  current: { sales: number; orders: number; avg: number; coupons: number };
  previous: { sales: number; orders: number; avg: number; coupons: number };
}

interface TrendPoint {
  label: string;
  title: string;
  sales: number;
  orders: number;
}

const pct = (curr: number, prev: number) =>
  prev === 0 ? "0.0" : (((curr - prev) / prev) * 100).toFixed(1);

const formatAxisMoney = (v: number) => (v >= 10000 ? `${v / 10000}만` : v.toLocaleString());

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

const TrendTooltip = ({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload: TrendPoint }> }) => {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md px-3 py-2">
      <p className="text-xs font-semibold text-gray-500 mb-1">{point.title}</p>
      <p className="text-sm font-black text-gray-900">₩{point.sales.toLocaleString()}</p>
      <p className="text-xs text-gray-400">{point.orders}건</p>
    </div>
  );
};

export const SalesStatus = () => {
  const [period, setPeriod] = useState<Period>("오늘");
  const [data, setData] = useState<SalesData | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    const load = () => {
      const param = PERIOD_PARAM[period];
      Promise.all([
        apiFetch<SalesData>(`/api/admin/sales?period=${param}`),
        apiFetch<TrendPoint[]>(`/api/admin/sales/trend?period=${param}`),
      ])
        .then(([sales, points]) => {
          setData(sales);
          setTrend(points);
          setError("");
        })
        .catch(() => setError("매출 데이터를 불러오지 못했습니다."))
        .finally(() => setLoading(false));
    };
    setLoading(true);
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [period]);

  const curr = data?.current;
  const prev = data?.previous;
  const trendRows = trend.filter((p) => p.orders > 0);

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

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm font-semibold rounded-lg px-4 py-2.5">{error}</div>
      )}

      {loading || !curr || !prev ? (
        !error && <div className="flex items-center justify-center h-40 text-gray-400 text-sm">불러오는 중...</div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
          {curr.orders === 0 ? (
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100 flex items-center justify-center">
              <p className="text-sm text-gray-400">해당 기간에 주문 데이터가 없습니다.</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <p className="text-sm font-bold text-gray-800">매출 추이</p>
                  <p className="text-xs text-gray-400">{TREND_SUBTITLE[period]} 매출액</p>
                </div>
                <button
                  onClick={() => setShowTable((v) => !v)}
                  className="text-xs font-semibold text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors shrink-0"
                >
                  {showTable ? "차트 보기" : "표 보기"}
                </button>
              </div>

              {showTable ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-gray-500 border-b border-gray-100">
                        <th className="text-left font-bold py-2">구간</th>
                        <th className="text-right font-bold py-2">주문 건수</th>
                        <th className="text-right font-bold py-2">매출액</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trendRows.map((p) => (
                        <tr key={p.title} className="border-b border-gray-50 text-gray-700">
                          <td className="py-2">{p.title}</td>
                          <td className="py-2 text-right tabular-nums">{p.orders}건</td>
                          <td className="py-2 text-right tabular-nums font-semibold">₩{p.sales.toLocaleString()}</td>
                        </tr>
                      ))}
                      <tr className="font-bold text-gray-900">
                        <td className="py-2">합계</td>
                        <td className="py-2 text-right tabular-nums">{curr.orders}건</td>
                        <td className="py-2 text-right tabular-nums">₩{curr.sales.toLocaleString()}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#F3F4F6" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#6B7280" }} axisLine={false} tickLine={false} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#6B7280" }}
                      axisLine={false}
                      tickLine={false}
                      width={44}
                      allowDecimals={false}
                      tickFormatter={formatAxisMoney}
                    />
                    <Tooltip content={<TrendTooltip />} cursor={{ fill: "#FFFBEB" }} />
                    <Bar dataKey="sales" fill={BAR_COLOR} radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};
