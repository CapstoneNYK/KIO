import { create } from "zustand";
import type { MenuItem, MenuOption, Temperature } from "../types/menu";

export interface CartItem {
  cartId: number;
  item: MenuItem;
  quantity: number;
  temperature: Temperature;
  options: MenuOption[];
  isPackaging: boolean;
}

interface CartStore {
  items: CartItem[];
  addItem: (item: MenuItem, quantity: number, temperature: Temperature, options: MenuOption[], isPackaging: boolean) => void;
  removeItem: (cartId: number) => void;
  updateQuantity: (cartId: number, quantity: number) => void;
  clear: () => void;
}

let nextId = 1;

export const useCartStore = create<CartStore>((set) => ({
  items: [],
  addItem: (item, quantity, temperature, options, isPackaging) =>
    set((state) => {
      const isSameOptions = (a: MenuOption[], b: MenuOption[]) => {
        if (a.length !== b.length) return false;
        return a.every((opt) => b.some((o) => o.name === opt.name && o.count === opt.count));
      };

      const existing = state.items.find(
        (i) =>
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

      return {
        items: [...state.items, { cartId: nextId++, item, quantity, temperature, options, isPackaging }],
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
