import { create } from "zustand";

import { API_URL } from "../api/base";

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
  /** 관리자에서 켜져 있는 할인수단 코드(kt/tmembership/uzu/cjone). 아직 못 불러왔으면 null(결제창은 전부 보여 준다) */
  methodCodes: string[] | null;
  loading: boolean;
  fetchDiscounts: () => Promise<void>;
}

export const useDiscountStore = create<DiscountState>((set) => ({
  posters: [],
  methodCodes: null,
  loading: true,
  fetchDiscounts: async () => {
    try {
      const res = await fetch(`${API_URL}/api/discounts`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: BackendDiscount[] = await res.json();
      const posters: Poster[] = data
        .filter((d) => d.image_url)
        .map((d) => ({ id: d.id, name: d.name, url: `${API_URL}${d.image_url}` }));
      set({ posters, methodCodes: data.map((d) => d.method_code), loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
