import { NavBar } from "../components/NavBar";
import { SpeechInput } from "../components/SpeechInput";
import { TopBar } from "../components/TopBar";
import { useState } from "react";
import { coffee1 } from "../assets";
import { Card } from "../components/Card";
import { MenuModal } from "../components/MenuModal";
import { CartBar } from "../components/CartBar";
import type { MenuItem } from "../types/menu";

export const Home = () => {
  const categories = [
    "전체",
    "커피",
    "디카페인",
    "스무디",
    "에이드",
    "주스",
    "티",
  ];

  const menus = [
    {
      id: 1,
      title: "아메리카노",
      price: 4000,
      img: coffee1,
    },
    {
      id: 2,
      title: "아메리카노",
      price: 4000,
      img: coffee1,
    },
    {
      id: 3,
      title: "아메리카노",
      price: 4000,
      img: coffee1,
    },
    {
      id: 4,
      title: "아메리카노",
      price: 4000,
      img: coffee1,
    },
  ];

  const [activeCategory, setActiveCategory] = useState("전체");
  const [selectedItem, setSelectedItem] = useState<MenuItem | null>(null);

  return (
    <div className="flex flex-col h-screen">
      <TopBar />
      <NavBar
        categories={categories}
        activeCategory={activeCategory}
        onSelect={setActiveCategory}
      />
      <div className="flex-1 overflow-y-auto grid grid-cols-2 gap-4 px-4 py-4 sm:grid-cols-3 lg:grid-cols-4 content-start">
        {menus.map((menu) => (
          <Card
            key={menu.id}
            img={menu.img}
            title={menu.title}
            price={menu.price}
            onClick={() => setSelectedItem(menu)}
          />
        ))}
      </div>

      ;<h1>STT Test</h1>
      <SpeechInput />

      <CartBar />

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
