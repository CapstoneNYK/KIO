import { create } from "zustand";
import type { MenuItem, MenuOption, Temperature } from "../types/menu";

export interface CartItem {
  cartId: number;
  item: MenuItem;
  quantity: number;
  temperature: Temperature;
  options: MenuOption[];
  isPackaging: boolean;
  isFree?: boolean;
}

interface CartStore {
  items: CartItem[];
  isPackaging: boolean;
  // 주문확인에서 먹고가기/가져가기를 아직 고르지 않았으면 false (기본값을 보여주지 않기 위함)
  packagingChosen: boolean;
  // 옵션으로 표현되지 않는 요청사항 메모 (주문확인 화면에 표시)
  memo: string;
  // 말로 "먹고 갈게요/포장할게요"라고 했을 때 주문확인에서 미리 강조해 줄 쪽
  packagingHint: "dine" | "take" | null;
  setPackagingHint: (v: "dine" | "take" | null) => void;
  addMemo: (m: string, menu?: string | null) => void;
  setIsPackaging: (v: boolean) => void;
  // 주문확인 창에서 먹고가기/가져가기를 고르면 장바구니 전체에 같은 값을 적용한다
  setPackagingAll: (v: boolean) => void;
  addItem: (item: MenuItem, quantity: number, temperature: Temperature, options: MenuOption[], isPackaging: boolean, isFree?: boolean) => void;
  removeItem: (cartId: number) => void;
  updateQuantity: (cartId: number, quantity: number) => void;
  updateTemperature: (cartId: number, temperature: Temperature) => void;
  updateOptions: (cartId: number, options: MenuOption[]) => void;
  clear: () => void;
}

let nextId = 1;

// 옵션 추가 금액. 서버(관리자 '메뉴 관리'에서 설정)에서 받아 menuStore 가 채운다. 못 받아도 기본 금액으로 계산한다
export const OPTION_PRICES: Record<string, number> = { 샷추가: 500 };

export const optionExtra = (options: MenuOption[]): number =>
  options.reduce((sum, o) => sum + (OPTION_PRICES[o.name] ?? 0) * o.count, 0);

export const unitPrice = (i: { item: { price: number }; options: MenuOption[] }): number =>
  i.item.price + optionExtra(i.options);

export const remainingStock = (items: CartItem[], menu: MenuItem, excludeCartId?: number): number => {
  if (menu.stock == null) return Infinity;
  const used = items
    .filter((i) => i.item.id === menu.id && i.cartId !== excludeCartId)
    .reduce((sum, i) => sum + i.quantity, 0);
  return Math.max(0, menu.stock - used);
};

export const useCartStore = create<CartStore>((set) => ({
  items: [],
  isPackaging: false,
  packagingChosen: false,
  memo: "",
  packagingHint: null,
  setPackagingHint: (v) => set({ packagingHint: v }),
  // 어느 음료에 대한 요청인지 알면 "[아이스 딸기 라떼] 우유는 저지방으로"처럼 이름을 붙여 관리자 주문내역에서 연결해 보여 준다
  addMemo: (m, menu) =>
    set((state) => {
      const entry = menu ? `[${menu}] ${m}` : m;
      return { memo: state.memo ? `${state.memo} / ${entry}` : entry };
    }),
  setIsPackaging: (v) => set({ isPackaging: v }),
  setPackagingAll: (v) =>
    set((state) => {
      const same = (a: MenuOption[], b: MenuOption[]) =>
        a.length === b.length && a.every((x) => b.some((o) => o.name === x.name && o.count === x.count));
      const merged: CartItem[] = [];
      for (const i of state.items) {
        const next = { ...i, isPackaging: v };
        // 포장 여부만 달라서 따로 있던 같은 줄은 하나로 합친다
        const twin = next.isFree
          ? undefined
          : merged.find(
              (m) => !m.isFree && m.item.id === next.item.id && m.temperature === next.temperature && same(m.options, next.options)
            );
        if (twin) twin.quantity += next.quantity;
        else merged.push(next);
      }
      return { isPackaging: v, packagingChosen: true, items: merged };
    }),
  addItem: (item, quantity, temperature, options, isPackaging, isFree = false) =>
    set((state) => {
      quantity = Math.min(quantity, remainingStock(state.items, item));
      if (quantity < 1) return state;
      const isSameOptions = (a: MenuOption[], b: MenuOption[]) => {
        if (a.length !== b.length) return false;
        return a.every((opt) => b.some((o) => o.name === opt.name && o.count === opt.count));
      };

      if (!isFree) {
        const existing = state.items.find(
          (i) =>
            !i.isFree &&
            i.item.id === item.id &&
            i.temperature === temperature &&
            i.isPackaging === isPackaging &&
            isSameOptions(i.options, options)
        );
        if (existing) {
          return {
            items: state.items.map((i) =>
              i.cartId === existing.cartId ? { ...i, quantity: i.quantity + quantity } : i
            ),
          };
        }
      }

      return {
        items: [...state.items, { cartId: nextId++, item, quantity, temperature, options, isPackaging, isFree }],
      };
    }),
  removeItem: (cartId) =>
    set((state) => ({ items: state.items.filter((i) => i.cartId !== cartId) })),
  updateQuantity: (cartId, quantity) =>
    set((state) => {
      const target = state.items.find((i) => i.cartId === cartId);
      if (!target) return state;
      const capped = Math.min(quantity, remainingStock(state.items, target.item, cartId));
      return { items: state.items.map((i) => (i.cartId === cartId ? { ...i, quantity: capped } : i)) };
    }),
  updateTemperature: (cartId, temperature) =>
    set((state) => ({
      items: state.items.map((i) => (i.cartId === cartId ? { ...i, temperature } : i)),
    })),
  updateOptions: (cartId, options) =>
    set((state) => {
      const same = (a: MenuOption[], b: MenuOption[]) =>
        a.length === b.length && a.every((x) => b.some((o) => o.name === x.name && o.count === x.count));
      const target = state.items.find((i) => i.cartId === cartId);
      if (!target) return state;
      const twin = state.items.find(
        (i) =>
          i.cartId !== cartId && !i.isFree && !target.isFree &&
          i.item.id === target.item.id && i.temperature === target.temperature &&
          i.isPackaging === target.isPackaging && same(i.options, options)
      );
      if (twin) {
        return {
          items: state.items
            .filter((i) => i.cartId !== cartId)
            .map((i) => (i.cartId === twin.cartId ? { ...i, quantity: i.quantity + target.quantity } : i)),
        };
      }
      return { items: state.items.map((i) => (i.cartId === cartId ? { ...i, options } : i)) };
    }),
  clear: () => set({ items: [], packagingChosen: false, packagingHint: null, memo: "" }),
}));
