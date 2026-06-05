import {
  coffee1,
  imgCafeLatte, imgCappuccino, imgVanillaLatte, imgCaramelMacchiato, imgEspresso,
  imgStrawberrySmoothie, imgMangoSmoothie, imgBlueberrySmoothie,
  imgLemonAde, imgGreengrapesAde, imgGapefruitAde,
  imgOrangejuice, imgMangoJuice, imgStrawberryBananaJuice,
  imgHibiscus, imgChamomile, imgEarlgrey, imgPeppermint,
} from "../assets";
import type { MenuItem } from "../types/menu";

export const CATEGORIES = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티"];

export const MENUS: MenuItem[] = [
  // 커피
  { id: 1,  title: "아메리카노",         price: 2000, img: coffee1,               category: "커피" },
  { id: 2,  title: "카페라떼",           price: 3000, img: imgCafeLatte,          category: "커피" },
  { id: 3,  title: "카푸치노",           price: 4500, img: imgCappuccino,         category: "커피" },
  { id: 4,  title: "바닐라라떼",         price: 5000, img: imgVanillaLatte,       category: "커피" },
  { id: 5,  title: "카라멜마키아토",     price: 5000, img: imgCaramelMacchiato,   category: "커피" },
  { id: 6,  title: "에스프레소",         price: 1500, img: imgEspresso,           category: "커피" },
  // 디카페인
  { id: 7,  title: "디카페인 아메리카노", price: 4500, img: coffee1,              category: "디카페인" },
  { id: 8,  title: "디카페인 라떼",      price: 5000, img: imgCafeLatte,          category: "디카페인" },
  { id: 9,  title: "디카페인 바닐라라떼", price: 5500, img: imgVanillaLatte,      category: "디카페인" },
  // 스무디
  { id: 10, title: "딸기 스무디",        price: 5500, img: imgStrawberrySmoothie, category: "스무디" },
  { id: 11, title: "망고 요거트 스무디", price: 5500, img: imgMangoSmoothie,      category: "스무디" },
  { id: 12, title: "블루베리 스무디",    price: 5500, img: imgBlueberrySmoothie,  category: "스무디" },
  // 에이드
  { id: 13, title: "레몬 에이드",        price: 4500, img: imgLemonAde,           category: "에이드" },
  { id: 14, title: "자몽 에이드",        price: 4500, img: imgGapefruitAde,       category: "에이드" },
  { id: 15, title: "청포도 에이드",      price: 4500, img: imgGreengrapesAde,     category: "에이드" },
  // 주스
  { id: 16, title: "오렌지 주스",        price: 4000, img: imgOrangejuice,        category: "주스" },
  { id: 17, title: "망고 주스",          price: 4500, img: imgMangoJuice,         category: "주스" },
  { id: 18, title: "딸기 바나나 주스",   price: 4500, img: imgStrawberryBananaJuice, category: "주스" },
  // 티
  { id: 19, title: "얼그레이",           price: 3000, img: imgEarlgrey,           category: "티" },
  { id: 20, title: "캐모마일",           price: 3000, img: imgChamomile,          category: "티" },
  { id: 21, title: "페퍼민트",           price: 3000, img: imgPeppermint,         category: "티" },
  { id: 22, title: "히비스커스",         price: 3000, img: imgHibiscus,           category: "티" },
];
