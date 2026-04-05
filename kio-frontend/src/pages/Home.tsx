import { NavBar } from "../components/NavBar";
import { SpeechInput } from "../components/SpeechInput";
import { TopBar } from "../components/TopBar";
import { useState } from "react";
import { coffee1 } from "../assets";
import { Card } from "../components/Card";

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

  return (
    <div>
      <TopBar />
      <NavBar
        categories={categories}
        activeCategory={activeCategory}
        onSelect={setActiveCategory}
      />
      <div className="grid grid-cols-2 gap-4 px-4 py-4 sm:grid-cols-3 lg:grid-cols-4">
        {menus.map((menu) => (
          <Card
            key={menu.id}
            img={menu.img}
            title={menu.title}
            price={menu.price}
          />
        ))}
      </div>
      ;<h1>STT Test</h1>
      <SpeechInput />
    </div>
  );
};
