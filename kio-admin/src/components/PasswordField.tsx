import { useState } from "react";
import { PiLockKeyBold, PiEyeBold, PiEyeSlashBold } from "react-icons/pi";

interface PasswordFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  autoFocus?: boolean;
}

export const PasswordField = ({
  value,
  onChange,
  placeholder = "비밀번호 입력",
  autoComplete,
  autoFocus,
}: PasswordFieldProps) => {
  const [visible, setVisible] = useState(false);

  return (
    <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2.5 focus-within:border-amber-400 transition-colors">
      <PiLockKeyBold size={16} className="text-gray-400 shrink-0" />
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        className="flex-1 text-sm outline-none min-w-0"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="text-gray-400 hover:text-gray-600 transition-colors shrink-0"
        tabIndex={-1}
        aria-label={visible ? "비밀번호 숨기기" : "비밀번호 보기"}
      >
        {visible ? <PiEyeSlashBold size={16} /> : <PiEyeBold size={16} />}
      </button>
    </div>
  );
};
