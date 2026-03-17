import { Outlet } from "react-router";

export default function App() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-gray-100">
      <div className="flex h-full w-full max-w-md flex-col overflow-y-auto bg-black p-5">
        <Outlet />
      </div>
    </div>
  );
}
