import { create } from "zustand";
import type { MenuItem } from "../types/menu";
import { getMenuImage } from "../data/menuImages";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const CATEGORIES = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티", "논커피"];

interface BackendMenu {
  id: number;
  name: string;
  price: number;
  category: string;
  temps: string[];
  sold_out: boolean;
  stock: number | null;
  image_url: string | null;
}

interface MenuState {
  menus: MenuItem[];
  loading: boolean;
  error: string | null;
  fetchMenus: () => Promise<void>;
}

export const useMenuStore = create<MenuState>((set) => ({
  menus: [],
  loading: true,
  error: null,
  fetchMenus: async () => {
    try {
      const res = await fetch(`${API_URL}/api/menus`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: BackendMenu[] = await res.json();
      const categoryRank = (category: string) => {
        const i = CATEGORIES.indexOf(category);
        return i === -1 ? CATEGORIES.length : i;
      };
      const menus: MenuItem[] = [...data]
        .sort((a, b) => categoryRank(a.category) - categoryRank(b.category) || a.id - b.id)
        .map((m) => ({
        id: m.id,
        title: m.name,
        price: m.price,
        img: m.image_url ? `${API_URL}${m.image_url}` : getMenuImage(m.name),
        category: m.category,
        temps: m.temps,
        soldOut: m.sold_out,
        stock: m.stock ?? null,
      }));
      set({ menus, loading: false, error: null });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "메뉴를 불러오지 못했습니다.",
      });
    }
  },
}));
