export interface ButtonProps {
  text: string;
  onClick: () => void;
  disabled?: boolean;
}

export const Button = ({ text, onClick, disabled }: ButtonProps) => {
  return (
    <button
      className="px-4 py-2 bg-pink-400 text-white rounded hover:bg-blue-600"
      onClick={onClick}
      disabled={disabled}
    >
      {text}
    </button>
  );
};
