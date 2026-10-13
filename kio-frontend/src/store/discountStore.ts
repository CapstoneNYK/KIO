import { create } from "zustand";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface BackendDiscount {
  id: number;
  name: string;
  method_code: string;
  description: string;
  active: boolean;
  image_url: string | null;
}

export interface Poster {
  id: number;
  name: string;
  url: string;
}

interface DiscountState {
  posters: Poster[];
  loading: boolean;
  fetchDiscounts: () => Promise<void>;
}

export const useDiscountStore = create<DiscountState>((set) => ({
  posters: [],
  loading: true,
  fetchDiscounts: async () => {
    try {
      const res = await fetch(`${API_URL}/api/discounts`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: BackendDiscount[] = await res.json();
      const posters: Poster[] = data
        .filter((d) => d.image_url)
        .map((d) => ({ id: d.id, name: d.name, url: `${API_URL}${d.image_url}` }));
      set({ posters, loading: false });
    } catch {
      // 실패해도 조용히 무시 — 첫 화면(Splash)이 번들 이미지로 대체 표시한다
      set({ loading: false });
    }
  },
}));
