import { create } from "zustand";
import type { MenuItem } from "../types/menu";
import { getMenuImage } from "../data/menuImages";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const CATEGORIES = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티"];

interface BackendMenu {
  id: number;
  name: string;
  price: number;
  category: string;
  temps: string[];
  sold_out: boolean;
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
      const menus: MenuItem[] = data.map((m) => ({
        id: m.id,
        title: m.name,
        price: m.price,
        img: m.image_url ? `${API_URL}${m.image_url}` : getMenuImage(m.name),
        category: m.category,
        temps: m.temps,
        soldOut: m.sold_out,
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
