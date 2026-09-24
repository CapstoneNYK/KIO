import {
  coffee1,
  imgCafeLatte, imgCappuccino, imgVanillaLatte, imgCaramelMacchiato, imgEspresso,
  imgStrawberrySmoothie, imgMangoSmoothie, imgBlueberrySmoothie,
  imgLemonAde, imgGreengrapesAde, imgGapefruitAde,
  imgOrangejuice, imgMangoJuice, imgStrawberryBananaJuice,
  imgHibiscus, imgChamomile, imgEarlgrey, imgPeppermint,
} from "../assets";

// 백엔드 menus 테이블에는 아직 이미지 필드가 없어서, 이름으로 기존 번들 이미지를 매칭한다.
// 관리자 페이지에서 새로 추가한 메뉴는 매칭되는 이미지가 없으므로 DEFAULT_MENU_IMAGE로 대체된다.
const MENU_IMAGES: Record<string, string> = {
  "아메리카노": coffee1,
  "카페라떼": imgCafeLatte,
  "카푸치노": imgCappuccino,
  "바닐라라떼": imgVanillaLatte,
  "카라멜마키아토": imgCaramelMacchiato,
  "에스프레소": imgEspresso,
  "디카페인 아메리카노": coffee1,
  "디카페인 라떼": imgCafeLatte,
  "디카페인 바닐라라떼": imgVanillaLatte,
  "딸기 스무디": imgStrawberrySmoothie,
  "망고 요거트 스무디": imgMangoSmoothie,
  "블루베리 스무디": imgBlueberrySmoothie,
  "레몬 에이드": imgLemonAde,
  "자몽 에이드": imgGapefruitAde,
  "청포도 에이드": imgGreengrapesAde,
  "오렌지 주스": imgOrangejuice,
  "망고 주스": imgMangoJuice,
  "딸기 바나나 주스": imgStrawberryBananaJuice,
  "얼그레이": imgEarlgrey,
  "캐모마일": imgChamomile,
  "페퍼민트": imgPeppermint,
  "히비스커스": imgHibiscus,
};

export const DEFAULT_MENU_IMAGE = coffee1;

export const getMenuImage = (name: string): string => MENU_IMAGES[name] ?? DEFAULT_MENU_IMAGE;
