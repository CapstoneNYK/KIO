import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, PieChart, Pie,
} from "recharts";
import type { PieLabelRenderProps } from "recharts";
import { apiFetch } from "../api";

const CATEGORY_COLORS: Record<string, string> = {
  커피: "#F5A623", 디카페인: "#EF4444", 스무디: "#10B981",
  에이드: "#3B82F6", 주스: "#8B5CF6", 티: "#EC4899",
};
const TEMP_COLORS: Record<string, string> = { ICE: "#60A5FA", HOT: "#F97316" };

interface AnalyticsData {
  top_menus: { name: string; count: number }[];
  category_data: { name: string; value: number }[];
  temp_data: { name: string; value: number }[];
  time_menus: { time: string; top: string; second: string }[];
}

const PieLabel = (props: PieLabelRenderProps) => {
  const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;
  if (percent === undefined || midAngle === undefined || innerRadius === undefined || outerRadius === undefined) return null;
  if ((percent as number) < 0.06) return null;
  const RADIAN = Math.PI / 180;
  const radius = (innerRadius as number) + ((outerRadius as number) - (innerRadius as number)) * 0.5;
  const x = (cx as number) + radius * Math.cos(-(midAngle as number) * RADIAN);
  const y = (cy as number) + radius * Math.sin(-(midAngle as number) * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={700}>
      {`${((percent as number) * 100).toFixed(0)}%`}
    </text>
  );
};

export const MenuAnalytics = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => {
      apiFetch<AnalyticsData>("/api/admin/analytics")
        .then(setData)
        .finally(() => setLoading(false));
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  if (loading) return <div className="flex items-center justify-center h-40 text-gray-400 text-sm">불러오는 중...</div>;

  if (!data || data.top_menus.length === 0) {
    return (
      <div className="bg-white rounded-xl p-12 shadow-sm border border-gray-100 flex items-center justify-center">
        <p className="text-sm text-gray-400">최근 7일간 주문 데이터가 없습니다.</p>
      </div>
    );
  }

  const categoryData = data.category_data.map((d) => ({ ...d, fill: CATEGORY_COLORS[d.name] ?? "#9CA3AF" }));
  const tempData = data.temp_data.map((d) => ({ ...d, fill: TEMP_COLORS[d.name] ?? "#9CA3AF" }));

  return (
    <div className="flex flex-col gap-6">
      {/* TOP 5 + Pies side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* TOP 5 */}
        <div className="lg:col-span-3 bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <p className="text-sm font-bold text-gray-800 mb-1">판매량 TOP 5</p>
          <p className="text-xs text-gray-400 mb-5">최근 7일 기준</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart layout="vertical" data={data.top_menus} margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 13, fill: "#4B5563" }} axisLine={false} tickLine={false} width={90} />
              <Bar dataKey="count" fill="#F5A623" radius={[0, 6, 6, 0]} maxBarSize={22}
                label={{ position: "right", fontSize: 12, fill: "#6B7280", formatter: (v: unknown) => `${v}잔` }} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pies */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex-1 bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs font-bold text-gray-800 mb-3">카테고리별 비율</p>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={110} height={110}>
                <PieChart>
                  <Pie data={categoryData} cx="50%" cy="50%" outerRadius={52} dataKey="value" labelLine={false} label={PieLabel} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-1.5">
                {categoryData.map((d) => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: d.fill }} />
                    <span className="text-xs text-gray-500">{d.name}</span>
                    <span className="text-xs font-bold text-gray-700 ml-auto">{d.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex-1 bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs font-bold text-gray-800 mb-3">온도 선호 비율</p>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={110} height={110}>
                <PieChart>
                  <Pie data={tempData} cx="50%" cy="50%" outerRadius={52} dataKey="value" labelLine={false} label={PieLabel} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2">
                {tempData.map((d) => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: d.fill }} />
                    <span className="text-xs text-gray-500">{d.name}</span>
                    <span className="text-xs font-bold text-gray-700 ml-auto">{d.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Time-based */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
        <p className="text-sm font-bold text-gray-800 mb-4">시간대별 인기 메뉴</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {data.time_menus.map((t) => (
            <div key={t.time} className="p-4 rounded-xl" style={{ backgroundColor: "#FFFBEB" }}>
              <p className="text-xs text-gray-400 mb-2">{t.time}</p>
              <p className="text-sm font-bold text-gray-800">{t.top}</p>
              <p className="text-xs text-gray-400 mt-1">{t.second}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
