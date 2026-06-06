export type Intent = "recommend" | "qa" | "order" | "coupon" | "payment";

export interface OrderInfo {
  menu: string | null;
  temperature: "ICE" | "HOT";
  quantity: number;
  options?: string[];
  needs_recommendation: boolean;
}

export interface AskResponse {
  question: string;
  intent: Intent;
  answer: string;
  orders?: OrderInfo[];
  recommended_menus?: string[];
  payment_method?: string | null;
  discount_tip?: string | null;
}

export const askApi = async (query: string, cartItems: string[] = []): Promise<AskResponse> => {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, cart_items: cartItems }),
  });
  if (!response.ok) throw new Error(`서버 오류: ${response.status}`);
  return response.json();
};
