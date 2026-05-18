import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { Home } from "./pages/Home.tsx";
import { Splash } from "./pages/Splash.tsx";
import { MenuDetail } from "./pages/MenuDetail.tsx";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: <Splash />,
      },
      {
        path: "home",
        element: <Home />,
      },
      {
        path: "home/menu",
        element: <MenuDetail />,
      },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <RouterProvider router={router} />
);
