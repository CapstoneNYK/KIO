import { Outlet } from "react-router";

export default function App() {
  return (
    <div className="min-h-screen w-full bg-white">
      <div className="w-full min-h-screen flex flex-col">
        <Outlet />
      </div>
    </div>
  );
}
