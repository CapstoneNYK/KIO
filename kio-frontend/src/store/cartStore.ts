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
  updateTemperature: (cartId: number, temperature: Temperature) => void;
  updateOptions: (cartId: number, options: MenuOption[]) => void;
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
  clear: () => set({ items: [] }),
}));
