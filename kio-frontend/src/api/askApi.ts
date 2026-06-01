export type Intent = "recommend" | "qa" | "order";

export interface OrderInfo {
  menu: string | null;
  temperature: "ICE" | "HOT";
  needs_recommendation: boolean;
}

export interface AskResponse {
  question: string;
  intent: Intent;
  answer: string;
  order?: OrderInfo;
}

export const askApi = async (query: string): Promise<AskResponse> => {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) throw new Error(`서버 오류: ${response.status}`);
  return response.json();
};
