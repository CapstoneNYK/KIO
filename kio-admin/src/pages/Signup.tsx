import { useState } from "react";
import { PiUserBold, PiKeyBold } from "react-icons/pi";
import { API, setToken } from "../api";
import { AuthCard } from "../components/AuthCard";
import { PasswordField } from "../components/PasswordField";

interface SignupProps {
  onSuccess: () => void;
  onGoToLogin: () => void;
}

export const Signup = ({ onSuccess, onGoToLogin }: SignupProps) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [signupCode, setSignupCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password || !signupCode.trim()) return;
    if (password !== passwordConfirm) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/admin/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          password,
          signup_code: signupCode.trim(),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const detail = body?.detail;
        const message = Array.isArray(detail)
          ? detail[0]?.msg ?? "회원가입에 실패했습니다."
          : detail ?? "회원가입에 실패했습니다.";
        throw new Error(message);
      }
      const data = await res.json();
      setToken(data.access_token);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard
      subtitle="관리자 회원가입"
      footer={
        <p className="text-center text-sm text-gray-400 mt-4">
          이미 계정이 있으신가요?{" "}
          <button
            type="button"
            onClick={onGoToLogin}
            className="font-semibold hover:underline"
            style={{ color: "#F5A623" }}
          >
            로그인
          </button>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-gray-500">아이디</label>
          <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2.5 focus-within:border-amber-400 transition-colors">
            <PiUserBold size={16} className="text-gray-400 shrink-0" />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="영문/숫자 4~20자"
              autoComplete="username"
              autoFocus
              className="flex-1 text-sm outline-none min-w-0"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-gray-500">비밀번호</label>
          <PasswordField
            value={password}
            onChange={setPassword}
            placeholder="8자 이상 입력"
            autoComplete="new-password"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-gray-500">비밀번호 확인</label>
          <PasswordField
            value={passwordConfirm}
            onChange={setPasswordConfirm}
            placeholder="비밀번호 다시 입력"
            autoComplete="new-password"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-gray-500">가입 코드</label>
          <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2.5 focus-within:border-amber-400 transition-colors">
            <PiKeyBold size={16} className="text-gray-400 shrink-0" />
            <input
              type="text"
              value={signupCode}
              onChange={(e) => setSignupCode(e.target.value)}
              placeholder="관리자 가입 코드 입력"
              className="flex-1 text-sm outline-none min-w-0"
            />
          </div>
        </div>

        {error && <p className="text-xs font-semibold text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="mt-2 py-2.5 rounded-lg font-bold text-sm text-white transition-colors hover:brightness-95 disabled:opacity-60"
          style={{ backgroundColor: "#F5A623" }}
        >
          {loading ? "가입 중..." : "회원가입"}
        </button>
      </form>
    </AuthCard>
  );
};
