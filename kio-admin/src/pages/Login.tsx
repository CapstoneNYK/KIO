import { useState } from "react";
import { PiUserBold } from "react-icons/pi";
import { API, setToken } from "../api";
import { AuthCard } from "../components/AuthCard";
import { PasswordField } from "../components/PasswordField";

interface LoginProps {
  onSuccess: () => void;
  onGoToSignup: () => void;
}

export const Login = ({ onSuccess, onGoToSignup }: LoginProps) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? "로그인에 실패했습니다.");
      }
      const data = await res.json();
      setToken(data.access_token);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard
      subtitle="관리자 페이지"
      footer={
        <p className="text-center text-sm text-gray-400 mt-4">
          계정이 없으신가요?{" "}
          <button
            type="button"
            onClick={onGoToSignup}
            className="font-semibold hover:underline"
            style={{ color: "#F5A623" }}
          >
            회원가입
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
              placeholder="아이디 입력"
              autoComplete="username"
              autoFocus
              className="flex-1 text-sm outline-none min-w-0"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-gray-500">비밀번호</label>
          <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        </div>

        {error && <p className="text-xs font-semibold text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="mt-2 py-2.5 rounded-lg font-bold text-sm text-white transition-colors hover:brightness-95 disabled:opacity-60"
          style={{ backgroundColor: "#F5A623" }}
        >
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>
    </AuthCard>
  );
};
