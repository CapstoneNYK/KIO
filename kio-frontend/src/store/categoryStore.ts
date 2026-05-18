import { create } from "zustand";

interface CategoryStore {
  activeCategory: string;
  setCategory: (cat: string) => void;
}

export const useCategoryStore = create<CategoryStore>((set) => ({
  activeCategory: "전체",
  setCategory: (cat) => set({ activeCategory: cat }),
}));
