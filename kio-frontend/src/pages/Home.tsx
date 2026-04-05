import { NavBar } from "../components/NavBar";
import { SpeechInput } from "../components/SpeechInput";
import { TopBar } from "../components/TopBar";
import { useState } from "react";

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

  const [activeCategory, setActiveCategory] = useState("전체");

  return (
    <div>
      <TopBar />
      <NavBar
        categories={categories}
        activeCategory={activeCategory}
        onSelect={setActiveCategory}
      />
      ;<h1>STT Test</h1>
      <SpeechInput />
    </div>
  );
};
