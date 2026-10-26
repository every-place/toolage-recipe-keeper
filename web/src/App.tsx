import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api, ApiError, type Me } from "./api";
import { SessionContext } from "./session";
import AuthPage from "./pages/AuthPage";
import RecipeBox from "./pages/RecipeBox";
import RecipeView from "./pages/RecipeView";
import Editor from "./pages/Editor";
import CookMode from "./pages/CookMode";
import Settings from "./pages/Settings";
import Menus from "./pages/Menus";
import MenuPage from "./pages/MenuPage";

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setMe(await api.me());
      setError("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      else setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (error && me === undefined) {
    return (
      <div className="auth">
        <div className="error">{error}</div>
        <button className="btn" onClick={refresh}>Try again</button>
      </div>
    );
  }
  if (me === undefined) return null;
  if (me === null) return <AuthPage onDone={refresh} />;

  return (
    <SessionContext.Provider value={{ me, refresh }}>
      <Routes>
        <Route path="/" element={<RecipeBox />} />
        <Route path="/new" element={<Editor />} />
        <Route path="/r/:id" element={<RecipeView />} />
        <Route path="/r/:id/edit" element={<Editor />} />
        <Route path="/r/:id/cook" element={<CookMode />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/menus" element={<Menus />} />
        <Route path="/menus/:id" element={<MenuPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SessionContext.Provider>
  );
}
