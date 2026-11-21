import { useEffect, useState } from "react";
import { apiFetch } from "../api";

interface Faq {
  id: number;
  question: string;
  keywords: string;
  answer: string;
  active: boolean;
}
type Draft = { question: string; keywords: string; answer: string; active: boolean };
const EMPTY: Draft = { question: "", keywords: "", answer: "", active: true };

// 키오스크가 LLM 없이 바로 답하는 매장 안내(화장실·와이파이·영업시간…). 손님 말에 키워드가 들어 있으면 답변을 그대로 말한다
export const FaqManagement = () => {
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null); // null: 새로 추가
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () =>
    apiFetch<Faq[]>("/api/admin/faqs")
      .then((d) => { setFaqs(d); setError(""); })
      .catch(() => setError("목록을 불러오지 못했어요."))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const reset = () => { setEditingId(null); setDraft(EMPTY); setError(""); };

  const save = async () => {
    if (!draft.question.trim() || !draft.keywords.trim() || !draft.answer.trim()) {
      setError("질문, 키워드, 답변을 모두 입력해 주세요.");
      return;
    }
    setSaving(true);
    try {
      await apiFetch(editingId === null ? "/api/admin/faqs" : `/api/admin/faqs/${editingId}`, {
        method: editingId === null ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      reset();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했어요.");
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (f: Faq) => {
    await apiFetch(`/api/admin/faqs/${f.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: !f.active }),
    }).catch(() => setError("변경하지 못했어요."));
    load();
  };

  const remove = async (f: Faq) => {
    if (!window.confirm(`"${f.question}" FAQ를 삭제할까요?`)) return;
    await apiFetch(`/api/admin/faqs/${f.id}`, { method: "DELETE" }).catch(() => setError("삭제하지 못했어요."));
    if (editingId === f.id) reset();
    load();
  };

  const input = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-amber-400";

  return (
    <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
      <div className="xl:col-span-3 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-gray-400 text-sm">불러오는 중...</div>
        ) : faqs.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-gray-400 text-sm">등록된 FAQ가 없어요. 오른쪽에서 추가해 보세요.</div>
        ) : (
          <ul>
            {faqs.map((f) => (
              <li key={f.id} className="px-4 py-3 border-b border-gray-50 last:border-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className={`font-semibold text-sm ${f.active ? "text-gray-800" : "text-gray-400 line-through"}`}>{f.question}</p>
                    <p className="text-xs text-gray-400 mt-0.5 break-all">키워드: {f.keywords}</p>
                    <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">{f.answer}</p>
                  </div>
                  <div className="flex gap-1.5 shrink-0 text-xs font-semibold">
                    <button onClick={() => toggle(f)} className="px-2 py-1 rounded-lg bg-gray-50 text-gray-500 hover:bg-gray-100">
                      {f.active ? "끄기" : "켜기"}
                    </button>
                    <button
                      onClick={() => { setEditingId(f.id); setDraft({ question: f.question, keywords: f.keywords, answer: f.answer, active: f.active }); setError(""); }}
                      className="px-2 py-1 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100"
                    >
                      수정
                    </button>
                    <button onClick={() => remove(f)} className="px-2 py-1 rounded-lg bg-red-50 text-red-500 hover:bg-red-100">삭제</button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="xl:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col gap-3 self-start">
        <p className="text-sm font-bold text-gray-800">{editingId === null ? "FAQ 추가" : "FAQ 수정"}</p>
        <label className="text-xs font-semibold text-gray-500">
          질문 (관리용 제목)
          <input className={`${input} mt-1`} value={draft.question} onChange={(e) => set("question", e.target.value)} placeholder="예: 화장실 위치" />
        </label>
        <label className="text-xs font-semibold text-gray-500">
          키워드 (쉼표로 구분, 하나라도 들어 있으면 답해요)
          <input className={`${input} mt-1`} value={draft.keywords} onChange={(e) => set("keywords", e.target.value)} placeholder="예: 화장실, 와이파이+비번" />
          <span className="block text-[11px] font-normal text-gray-400 mt-1">+ 로 묶으면 전부 들어 있어야 해요. 띄어쓰기는 무시돼요.</span>
        </label>
        <label className="text-xs font-semibold text-gray-500">
          답변 (키오스크가 그대로 말해요)
          <textarea className={`${input} mt-1 h-24 resize-none`} value={draft.answer} onChange={(e) => set("answer", e.target.value)} placeholder="예: 화장실은 매장 안쪽 왼편에 있어요." />
          <span className="block text-[11px] font-normal text-gray-400 mt-1">**중요한 말**처럼 별표 두 개로 감싸면 굵게 보여요.</span>
        </label>
        <label className="flex items-center gap-2 text-xs font-semibold text-gray-500">
          <input type="checkbox" checked={draft.active} onChange={(e) => set("active", e.target.checked)} /> 사용
        </label>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex gap-2">
          <button onClick={save} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-bold text-white disabled:opacity-50" style={{ backgroundColor: "#F5A623" }}>
            {saving ? "저장 중..." : editingId === null ? "추가" : "저장"}
          </button>
          {(editingId !== null || draft !== EMPTY) && (
            <button onClick={reset} className="px-4 py-2 rounded-lg text-sm font-semibold bg-gray-100 text-gray-500 hover:bg-gray-200">취소</button>
          )}
        </div>
      </div>
    </div>
  );
};
