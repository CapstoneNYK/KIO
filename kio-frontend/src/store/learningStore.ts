import { create } from "zustand";

interface LearningStore {
  learningScreen: string | null;
  setLearningScreen: (screen: string | null) => void;
  guideScreen: string | null;
  setGuideScreen: (screen: string | null) => void;
  highlightPaymentMethod: string | null;
  setHighlightPaymentMethod: (method: string | null) => void;
  orderOverlayOpen: boolean;
  setOrderOverlayOpen: (v: boolean) => void;
  paymentDetailOverlayOpen: boolean;
  setPaymentDetailOverlayOpen: (v: boolean) => void;
  dismissPaymentOverlay: () => void;
}

export const useLearningStore = create<LearningStore>((set) => ({
  learningScreen: null,
  setLearningScreen: (screen) => set({ learningScreen: screen }),
  guideScreen: null,
  setGuideScreen: (screen) => set({ guideScreen: screen }),
  highlightPaymentMethod: null,
  setHighlightPaymentMethod: (method) => set({ highlightPaymentMethod: method }),
  orderOverlayOpen: false,
  setOrderOverlayOpen: (v) => set({ orderOverlayOpen: v }),
  paymentDetailOverlayOpen: false,
  setPaymentDetailOverlayOpen: (v) => set({ paymentDetailOverlayOpen: v }),
  dismissPaymentOverlay: () => set({ guideScreen: null, highlightPaymentMethod: null, orderOverlayOpen: false, paymentDetailOverlayOpen: false }),
}));
