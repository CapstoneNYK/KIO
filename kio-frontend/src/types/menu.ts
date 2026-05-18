export interface MenuItem {
  id: number;
  title: string;
  price: number;
  img: string;
  category?: string;
}

export type Temperature = "HOT" | "ICE";

export interface MenuOption {
  name: string;
  count: number;
}
