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
  setIsPackaging: (v: boolean) => void;
  addItem: (item: MenuItem, quantity: number, temperature: Temperature, options: MenuOption[], isPackaging: boolean, isFree?: boolean) => void;
  removeItem: (cartId: number) => void;
  updateQuantity: (cartId: number, quantity: number) => void;
  clear: () => void;
}

let nextId = 1;

export const useCartStore = create<CartStore>((set) => ({
  items: [],
  isPackaging: false,
  setIsPackaging: (v) => set({ isPackaging: v }),
  addItem: (item, quantity, temperature, options, isPackaging, isFree = false) =>
    set((state) => {
      const isSameOptions = (a: MenuOption[], b: MenuOption[]) => {
        if (a.length !== b.length) return false;
        return a.every((opt) => b.some((o) => o.name === opt.name && o.count === opt.count));
      };

      // 무료 아이템은 중복 병합 없이 항상 새 항목으로 추가
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
    set((state) => ({
      items: state.items.map((i) => (i.cartId === cartId ? { ...i, quantity } : i)),
    })),
  clear: () => set({ items: [] }),
}));
