import { NavBar } from "../components/NavBar";
import { TopBar } from "../components/TopBar";
import { useState, useEffect } from "react";
import { useCategoryStore } from "../store/categoryStore";
import { useLearningStore } from "../store/learningStore";
import { useCartStore } from "../store/cartStore";
import { Card } from "../components/Card";
import { MenuModal } from "../components/MenuModal";
import { CartBar } from "../components/CartBar";
import { PaymentModal } from "../components/PaymentModal";
import { MENUS, CATEGORIES } from "../data/menus";
import type { MenuItem } from "../types/menu";

const PAYMENT_GUIDE_SCREENS = ["payment", "payment_card", "payment_complete"];

export const Home = () => {
  const { activeCategory, setCategory: setActiveCategory } = useCategoryStore();
  const [selectedItem, setSelectedItem] = useState<MenuItem | null>(null);
  const learningScreen = useLearningStore((s) => s.learningScreen);
  const guideScreen = useLearningStore((s) => s.guideScreen);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const cartItems = useCartStore((s) => s.items);

  // 장바구니가 비어있을 때 결제 안내용 독립 모달
  const showStandalonePayment =
    PAYMENT_GUIDE_SCREENS.includes(guideScreen ?? "") && cartItems.length === 0;

  useEffect(() => {
    if (learningScreen === "menu_modal") {
      setSelectedItem(MENUS[0]);
    } else if (learningScreen === null || learningScreen === "splash" || learningScreen.startsWith("home_")) {
      setSelectedItem(null);
    }
  }, [learningScreen]);

  useEffect(() => {
    if (guideScreen === "menu_modal") setSelectedItem(MENUS[0]);
  }, [guideScreen]);

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
            onClick={() => setSelectedItem(menu)}
          />
        ))}
      </div>

      <CartBar />

      {selectedItem && (
        <MenuModal
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onOrder={() => setSelectedItem(null)}
        />
      )}

      {/* 장바구니가 비어있을 때 결제 안내용 독립 PaymentModal */}
      {showStandalonePayment && (
        <PaymentModal
          onClose={() => setGuideScreen(null)}
          onSelect={() => setGuideScreen(null)}
        />
      )}
    </div>
  );
};
