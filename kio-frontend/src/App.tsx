import { Outlet } from "react-router-dom";
import { AssistantButton } from "./components/AssistantButton";

export default function App() {
  return (
    <div className="min-h-screen w-full bg-[#FFEFCE]">
      <AssistantButton />
      <div className="w-full min-h-screen flex flex-col">
        <Outlet />
      </div>
    </div>
  );
}
