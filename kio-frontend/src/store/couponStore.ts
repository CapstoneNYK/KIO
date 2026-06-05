import { create } from "zustand";

export type AppliedCoupon =
  | { code: string; type: "product"; menu: string; menuPrice: number; description: string }
  | { code: string; type: "amount"; balance: number; description: string };

interface CouponStore {
  coupons: AppliedCoupon[];
  addCoupon: (c: AppliedCoupon) => void;
  removeCoupon: (code: string) => void;
  clearCoupons: () => void;
  scanOpen: boolean;
  scanSource: "assistant" | "payment";
  openScan: (source?: "assistant" | "payment") => void;
  closeScan: () => void;
}

export const useCouponStore = create<CouponStore>((set) => ({
  coupons: [],
  addCoupon: (c) =>
    set((s) => {
      if (s.coupons.find((x) => x.code === c.code)) return s;
      return { coupons: [...s.coupons, c] };
    }),
  removeCoupon: (code) =>
    set((s) => ({ coupons: s.coupons.filter((c) => c.code !== code) })),
  clearCoupons: () => set({ coupons: [] }),
  scanOpen: false,
  scanSource: "payment",
  openScan: (source = "payment") => set({ scanOpen: true, scanSource: source }),
  closeScan: () => set({ scanOpen: false }),
}));

export function calcDiscount(coupons: AppliedCoupon[], cartTotal: number): number {
  let total = 0;
  for (const c of coupons) {
    total += c.type === "product" ? c.menuPrice : c.balance;
  }
  return Math.min(total, cartTotal);
}
