export interface NavBarProps {
  categories: string[];
  activeCategory: string;
  onSelect: (category: string) => void;
}

export const NavBar = ({
  categories,
  activeCategory,
  onSelect,
}: NavBarProps) => {
  return (
    <div className="flex gap-2 overflow-x-auto px-4 py-2 bg-[#FFF9F1]">
      {categories.map((category) => {
        const isActive = category === activeCategory;

        return (
          <button
            key={category}
            onClick={() => onSelect(category)}
            className={`
                whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium cursor-pointer
                transition
                ${
                  isActive
                    ? "bg-yellow-400 text-white"
                    : "border border-yellow-300 bg-white text-gray-700"
                }
              `}
          >
            {category}
          </button>
        );
      })}
    </div>
  );
};
