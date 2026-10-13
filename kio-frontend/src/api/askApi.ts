export type Intent = "recommend" | "qa" | "order" | "coupon" | "payment" | "order_and_pay" | "cancel" | "modify";

export interface OptionDetail {
  kind: string;
  name: string;
  count: number;
}

export interface OrderInfo {
  menu: string | null;
  temperature: "ICE" | "HOT";
  quantity: number;
  options?: string[];
  option_details?: OptionDetail[]; // 샷 개수, 시럽·크림 양, 사이즈 등 구조화된 옵션
  packaging?: boolean | null;
  needs_recommendation: boolean;
}

// 장바구니 취소·변경 명령 (백엔드가 규칙 기반으로 해석해서 내려준다)
export type CartAction =
  | { type: "remove_all" }
  | { type: "remove_last" }
  | { type: "remove_item"; menu: string; temperature?: "ICE" | "HOT" | null }
  | { type: "set_quantity"; menu: string; quantity: number; temperature?: "ICE" | "HOT" | null }
  | { type: "set_temperature"; menu: string; temperature: "ICE" | "HOT" }
  | { type: "replace_item"; menu: string; to_menu: string };

export interface AskResponse {
  question: string;
  intent: Intent;
  answer: string;
  orders?: OrderInfo[];
  recommended_menus?: string[];
  payment_method?: string | null;
  discount_tip?: string | null;
  cart_actions?: CartAction[];
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
