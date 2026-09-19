export interface CardProps {
  img: string;
  title: string;
  price: number;
  soldOut?: boolean;
  onClick?: () => void;
}

export const Card = ({ img, title, price, soldOut, onClick }: CardProps) => {
  return (
    <button
      onClick={soldOut ? undefined : onClick}
      disabled={soldOut}
      className="
          relative w-full rounded-2xl bg-white p-4
          shadow-sm transition
          active:scale-95
          focus:outline-none
          disabled:opacity-60
        "
    >
      {soldOut && (
        <span className="absolute top-3 right-3 z-10 rounded-full bg-gray-500 px-2.5 py-1 text-xs font-bold text-white">
          품절
        </span>
      )}
      <img
        src={img}
        alt={title}
        className="h-40 w-full rounded-xl object-contain"
      />

      <div className="mt-3 text-left">
        <p className="text-base font-semibold text-gray-900">{title}</p>
        <p className="mt-1 text-sm font-bold text-orange-500">
          {price.toLocaleString()}원
        </p>
      </div>
    </button>
  );
};
