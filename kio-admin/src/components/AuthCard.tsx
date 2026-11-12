import type { ReactNode } from "react";
import { PiStorefrontBold } from "react-icons/pi";

interface AuthCardProps {
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}

export const AuthCard = ({ subtitle, children, footer }: AuthCardProps) => {
  return (
    <div className="flex h-screen items-center justify-center" style={{ backgroundColor: "#F8F7F5" }}>
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <div className="flex flex-col items-center gap-3 mb-8">
          <div
            className="w-14 h-14 rounded-xl flex items-center justify-center font-black text-sm text-white tracking-wider"
            style={{ backgroundColor: "#F5A623" }}
          >
            NYK
          </div>
          <div className="text-center">
            <p className="font-bold text-gray-900 text-lg leading-tight">NYK CAFE</p>
            <p className="text-xs text-gray-400 leading-tight mt-0.5">{subtitle}</p>
          </div>
        </div>

        {children}

        {footer}

        <div className="flex items-center justify-center gap-1.5 mt-6 text-[10px] text-gray-400">
          <PiStorefrontBold size={12} />
          NYK CAFE 1호점
        </div>
      </div>
    </div>
  );
};
