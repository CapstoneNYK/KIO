export type Intent = "recommend" | "qa" | "order" | "coupon" | "payment" | "order_and_pay" | "cancel" | "modify" | "dialog";

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
  option_details?: OptionDetail[];
  packaging?: boolean | null;
  needs_recommendation: boolean;
}

export type CartAction =
  | { type: "remove_all" }
  | { type: "remove_last" }
  | { type: "remove_item"; menu: string; temperature?: "ICE" | "HOT" | null }
  | { type: "set_quantity"; menu: string; quantity: number; temperature?: "ICE" | "HOT" | null }
  | { type: "set_temperature"; menu: string; temperature: "ICE" | "HOT" }
  | { type: "set_temperature_part"; menu: string; temperature: "ICE" | "HOT"; count: number }
  | { type: "set_temperature_all"; temperature: "ICE" | "HOT"; menus: string[] }
  | { type: "replace_item"; menu: string; to_menu: string }
  | { type: "remove_line"; indexes: number[] }
  | { type: "set_options"; index: number; count: number; options: { name: string; count: number }[] };

// 서버가 만든 옵션 되묻기 대화 상태. 내용은 몰라도 되고 다음 요청에 그대로 되돌려 보낸다.
export type DialogState = Record<string, unknown>;

export interface AskResponse {
  question: string;
  intent: Intent;
  answer: string;
  orders?: OrderInfo[];
  recommended_menus?: string[];
  payment_method?: string | null;
  cart_actions?: CartAction[];
  dialog?: DialogState | null;
  go_payment?: boolean;
}

export const sendFeedback = async (query: string, answer: string, intent: string): Promise<void> => {
  await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, answer, intent }),
  });
};

export const askApi = async (
  query: string,
  cartItems: string[] = [],
  dialog: DialogState | null = null,
): Promise<AskResponse> => {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, cart_items: cartItems, dialog }),
  });
  if (!response.ok) throw new Error(`서버 오류: ${response.status}`);
  return response.json();
};
