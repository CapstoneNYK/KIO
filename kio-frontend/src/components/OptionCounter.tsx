interface OptionCounterProps {
  count: number;
  onDecrement: () => void;
  onIncrement: () => void;
  min?: number;
}

export const OptionCounter = ({
  count,
  onDecrement,
  onIncrement,
  min = 0,
}: OptionCounterProps) => {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onDecrement}
        disabled={count <= min}
        className="w-10 h-10 rounded flex items-center justify-center text-lg disabled:opacity-30 active:opacity-70"
        style={{ border: "1.5px solid #FEE685", color: "#E17100" }}
      >
        -
      </button>
      <span className="w-8 text-center text-lg">{count}</span>
      <button
        onClick={onIncrement}
        className="w-10 h-10 rounded flex items-center justify-center text-lg active:opacity-70"
        style={{ border: "1.5px solid #FEE685", color: "#E17100" }}
      >
        +
      </button>
    </div>
  );
};
