import { NavBar } from "../components/NavBar";
import { TopBar } from "../components/TopBar";
import { useState } from "react";
import { useCategoryStore } from "../store/categoryStore";
import {
  coffee1,
  imgCafeLatte, imgCappuccino, imgVanillaLatte, imgCaramelMacchiato, imgEspresso,
  imgStrawberrySmoothie, imgMangoSmoothie, imgBlueberrySmoothie,
  imgLemonAde, imgGreengrapesAde, imgGapefruitAde, 
  imgOrangejuice, imgCarrotjuice,
  imgHibiscus, imgChamomile, imgEarlgrey, imgPeppermint,
  imgApplejuice,
} from "../assets";
import { Card } from "../components/Card";
import { MenuModal } from "../components/MenuModal";
import { CartBar } from "../components/CartBar";
import type { MenuItem } from "../types/menu";

const CATEGORIES = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티"];

const MENUS: MenuItem[] = [
  // 커피
  { id: 1,  title: "아메리카노",      price: 2000, img: coffee1,              category: "커피" },
  { id: 2,  title: "카페라떼",        price: 3000, img: imgCafeLatte,         category: "커피" },
  { id: 3,  title: "카푸치노",        price: 4500, img: imgCappuccino,        category: "커피" },
  { id: 4,  title: "바닐라라떼",      price: 5000, img: imgVanillaLatte,      category: "커피" },
  { id: 5,  title: "카라멜마키아토",  price: 5000, img: imgCaramelMacchiato, category: "커피" },
  { id: 6,  title: "에스프레소",      price: 1500, img: imgEspresso,          category: "커피" },
  // 디카페인
  { id: 7,  title: "디카페인 아메리카노", price: 4500, img: coffee1,         category: "디카페인" },
  { id: 8,  title: "디카페인 라떼",       price: 5000, img: imgCafeLatte,    category: "디카페인" },
  { id: 9,  title: "디카페인 바닐라라떼", price: 5500, img: imgVanillaLatte, category: "디카페인" },
  // 스무디
  { id: 10, title: "딸기 스무디",     price: 5500, img: imgStrawberrySmoothie,  category: "스무디" },
  { id: 11, title: "망고 스무디",     price: 5500, img: imgMangoSmoothie,       category: "스무디" },
  { id: 12, title: "블루베리 스무디", price: 5500, img: imgBlueberrySmoothie,   category: "스무디" },
  // 에이드
  { id: 13, title: "레몬 에이드",     price: 4500, img: imgLemonAde, category: "에이드" },
  { id: 14, title: "자몽 에이드",     price: 4500, img: imgGapefruitAde,     category: "에이드" },
  { id: 15, title: "청포도 에이드",   price: 4500, img: imgGreengrapesAde,     category: "에이드" },
  // 주스
  { id: 16, title: "오렌지 주스",     price: 4000, img: imgOrangejuice, category: "주스" },
  { id: 17, title: "사과 주스",       price: 4000, img: imgApplejuice, category: "주스" },
  { id: 18, title: "당근 주스",       price: 4500, img: imgCarrotjuice, category: "주스" },
  // 티
  { id: 19, title: "얼그레이",        price: 3000, img: imgEarlgrey,      category: "티" },
  { id: 20, title: "캐모마일",        price: 3000, img: imgChamomile,      category: "티" },
  { id: 21, title: "페퍼민트",        price: 3000, img: imgPeppermint,      category: "티" },
  { id: 22, title: "히비스커스",      price: 3000, img: imgHibiscus,  category: "티" },
];

export const Home = () => {
  const { activeCategory, setCategory: setActiveCategory } = useCategoryStore();
  const [selectedItem, setSelectedItem] = useState<MenuItem | null>(null);

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
    </div>
  );
};
