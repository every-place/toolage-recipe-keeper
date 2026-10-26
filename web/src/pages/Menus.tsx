import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { menuApi, type MenuSummary } from "../api";

export default function Menus() {
  const navigate = useNavigate();
  const [menus, setMenus] = useState<MenuSummary[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    menuApi.list().then((d) => setMenus(d.menus)).catch((e) => setError(e.message));
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      const m = await menuApi.create(name || "This week");
      navigate(`/menus/${m.id}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <header className="topbar">
        <Link to="/" className="icon-btn" aria-label="Back to the recipe box">←</Link>
        <h1>Menus</h1>
      </header>
      <main className="page narrow">
        <p className="hint" style={{ marginTop: 0 }}>
          Plan what you're making, and Recipe Keeper builds one shopping list from all of it.
        </p>
        {error && <div className="error">{error}</div>}
        <form className="card row" onSubmit={create} style={{ alignItems: "center" }}>
          <input className="input" style={{ flex: "3 1 180px" }} value={name} onChange={(e) => setName(e.target.value)} placeholder="This week, Christmas baking…" />
          <button className="btn primary">New menu</button>
        </form>
        <ul className="list-plain">
          {menus?.map((m) => (
            <li key={m.id}>
              <Link to={`/menus/${m.id}`} style={{ flex: 1, textDecoration: "none", minHeight: 44, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <b>{m.name}</b>
                <span className="hint">{m.recipe_count} recipe{m.recipe_count === 1 ? "" : "s"}</span>
              </Link>
              <span aria-hidden>›</span>
            </li>
          ))}
        </ul>
        {menus && menus.length === 0 && <p className="hint">No menus yet.</p>}
      </main>
    </>
  );
}
