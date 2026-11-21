import { create } from "zustand";
import type { MenuItem } from "../types/menu";
import { getMenuImage } from "../data/menuImages";

import { API_URL } from "../api/base";

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
  /** 탭에 보여 줄 카테고리("전체" + 서버(DB)에 정해 둔 순서) */
  categories: string[];
  loading: boolean;
  error: string | null;
  fetchMenus: () => Promise<void>;
}

export const useMenuStore = create<MenuState>((set) => ({
  menus: [],
  categories: ["전체"],
  loading: true,
  error: null,
  fetchMenus: async () => {
    try {
      const res = await fetch(`${API_URL}/api/menus`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: BackendMenu[] = await res.json();
      // 카테고리 순서는 서버(DB)가 정한다. 못 받으면 메뉴에 나온 순서로 대신한다
      let order: string[] = [];
      try {
        const cres = await fetch(`${API_URL}/api/categories`);
        if (cres.ok) order = await cres.json();
      } catch { /* 아래에서 메뉴 기준으로 대신 */ }
      if (order.length === 0) order = [...new Set(data.map((m) => m.category))];
      const categoryRank = (category: string) => {
        const i = order.indexOf(category);
        return i === -1 ? order.length : i;
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
      set({ menus, categories: ["전체", ...order], loading: false, error: null });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "메뉴를 불러오지 못했습니다.",
      });
    }
  },
}));
