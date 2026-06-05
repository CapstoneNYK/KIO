import { NavBar } from "../components/NavBar";
import { TopBar } from "../components/TopBar";
import { useState } from "react";
import { useCategoryStore } from "../store/categoryStore";
import { useLearningStore } from "../store/learningStore";
import { useCartStore } from "../store/cartStore";
import { Card } from "../components/Card";
import { MenuModal } from "../components/MenuModal";
import { CartBar } from "../components/CartBar";
import { CouponScanner } from "../components/CouponScanner";
import { useCouponStore } from "../store/couponStore";
import { PaymentModal } from "../components/PaymentModal";
import { MENUS, CATEGORIES } from "../data/menus";
import type { MenuItem } from "../types/menu";

const PAYMENT_GUIDE_SCREENS = ["payment", "payment_card", "payment_complete"];

export const Home = () => {
  const { activeCategory, setCategory: setActiveCategory } = useCategoryStore();
  const [userSelectedItem, setUserSelectedItem] = useState<MenuItem | null>(null);
  const { scanOpen, closeScan } = useCouponStore();
  const learningScreen = useLearningStore((s) => s.learningScreen);
  const guideScreen = useLearningStore((s) => s.guideScreen);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const cartItems = useCartStore((s) => s.items);

  const showStandalonePayment =
    PAYMENT_GUIDE_SCREENS.includes(guideScreen ?? "") && cartItems.length === 0;

  const learningForcesReset =
    learningScreen === null || learningScreen === "splash" || (learningScreen?.startsWith("home_") ?? false);

  const selectedItem =
    learningScreen === "menu_modal" || guideScreen === "menu_modal"
      ? MENUS[0]
      : learningForcesReset
        ? null
        : userSelectedItem;

  const filteredMenus = activeCategory === "전체"
    ? MENUS
    : MENUS.filter((m) => m.category === activeCategory);

  return (
    <div className="flex flex-col h-screen">
      <TopBar />
      <NavBar
        categories={CATEGORIES}
        activeCategory={activeCategory}
        onSelect={setActiveCategory}
      />
      <div className="flex-1 overflow-y-auto grid grid-cols-2 gap-4 px-4 py-4 sm:grid-cols-3 lg:grid-cols-4 content-start">
        {filteredMenus.map((menu) => (
          <Card
            key={menu.id}
            img={menu.img}
            title={menu.title}
            price={menu.price}
            onClick={() => setUserSelectedItem(menu)}
          />
        ))}
      </div>

      <CartBar />

      {selectedItem && (
        <MenuModal
          item={selectedItem}
          onClose={() => setUserSelectedItem(null)}
          onOrder={() => setUserSelectedItem(null)}
        />
      )}

      {scanOpen && <CouponScanner onClose={closeScan} />}

      {showStandalonePayment && (
        <PaymentModal
          onClose={() => setGuideScreen(null)}
          onSelect={() => setGuideScreen(null)}
        />
      )}
    </div>
  );
};
