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
    set((state) => ({
      items: [...state.items, { cartId: nextId++, item, quantity, temperature, options, isPackaging }],
    })),
  removeItem: (cartId) =>
    set((state) => ({ items: state.items.filter((i) => i.cartId !== cartId) })),
  updateQuantity: (cartId, quantity) =>
    set((state) => ({
      items: state.items.map((i) => (i.cartId === cartId ? { ...i, quantity } : i)),
    })),
  clear: () => set({ items: [] }),
}));
