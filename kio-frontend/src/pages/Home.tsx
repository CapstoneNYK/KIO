import { NavBar } from "../components/NavBar";
import { TopBar } from "../components/TopBar";
import { useState } from "react";
import { useCategoryStore } from "../store/categoryStore";
import { Card } from "../components/Card";
import { MenuModal } from "../components/MenuModal";
import { CartBar } from "../components/CartBar";
import { SpeechInput } from "../components/SpeechInput";
import { MENUS, CATEGORIES } from "../data/menus";
import type { MenuItem } from "../types/menu";

export const Home = () => {
  const { activeCategory, setCategory: setActiveCategory } = useCategoryStore();
  const [selectedItem, setSelectedItem] = useState<MenuItem | null>(null);
  const [voiceOpen, setVoiceOpen] = useState(false);

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

      {/* 음성 주문 플로팅 버튼 */}
      <div className="fixed bottom-24 left-4 z-50">
        <button
          onClick={() => setVoiceOpen((v) => !v)}
          className={`
            w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all duration-200
            ${voiceOpen
              ? "bg-amber-600 ring-4 ring-amber-300"
              : "bg-amber-500 hover:bg-amber-600 hover:scale-105"}
          `}
          title="음성 주문"
        >
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1 17.93A8.001 8.001 0 0 1 4 11H6a6 6 0 0 0 12 0h2a8.001 8.001 0 0 1-7 7.93V22h2v2H9v-2h2v-2.07z" />
          </svg>
        </button>

        {voiceOpen && (
          <div className="absolute bottom-16 left-0 bg-white rounded-2xl shadow-xl p-4 w-80">
            <div className="flex justify-between items-center mb-3">
              <p className="text-sm font-bold text-gray-700">음성 주문</p>
              <button
                onClick={() => setVoiceOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              >
                ✕
              </button>
            </div>
            <SpeechInput />
          </div>
        )}
      </div>

      {selectedItem && (
        <MenuModal
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onOrder={() => setSelectedItem(null)}
        />
      )}
    </div>
  );
};
