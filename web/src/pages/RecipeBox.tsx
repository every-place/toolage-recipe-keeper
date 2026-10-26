import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, photoUrl, type RecipeSummary } from "../api";
import { useSession } from "../session";

export default function RecipeBox() {
  const { me } = useSession();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [recipes, setRecipes] = useState<RecipeSummary[] | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .listRecipes(q, category)
        .then((d) => {
          setRecipes(d.recipes);
          if (!q && !category) setCategories(d.categories);
          setError("");
        })
        .catch((e) => setError(e.message));
    }, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [q, category]);

  const filtering = q || category;

  return (
    <>
      <header className="topbar">
        <h1><span className="brand">Recipe Keeper</span></h1>
        <Link to="/settings" className="icon-btn" aria-label="Settings">⚙︎</Link>
      </header>
      <main className="page">
        <p className="hint" style={{ margin: "0 0 12px" }}>{me.household.name}</p>
        <div className="search">
          <input className="input" type="search" placeholder="Search recipes, ingredients, people…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {categories.length > 0 && (
          <div className="chips">
            <button className={`chip ${!category ? "on" : ""}`} onClick={() => setCategory("")}>All</button>
            {categories.map((c) => (
              <button key={c} className={`chip ${category === c ? "on" : ""}`} onClick={() => setCategory(c)}>{c}</button>
            ))}
          </div>
        )}
        {error && <div className="error">{error}</div>}
        {recipes && recipes.length === 0 && !filtering && (
          <div className="empty">
            <h2>Your recipe box is empty</h2>
            <p>Start with the one you make most, or the card that's most worn.</p>
            <Link to="/new" className="btn primary">Add your first recipe</Link>
          </div>
        )}
        {recipes && recipes.length === 0 && filtering && <div className="empty">No recipes match.</div>}
        <div className="grid">
          {recipes?.map((r) => (
            <Link key={r.id} to={`/r/${r.id}`} className="tile">
              <div className="photo" style={r.hero_photo_id ? { backgroundImage: `url(${photoUrl(r.hero_photo_id)})` } : undefined}>
                {!r.hero_photo_id && "🍪"}
              </div>
              <div className="body">
                <h3>{r.title}</h3>
                {r.source_person && <div className="from">from {r.source_person}</div>}
              </div>
            </Link>
          ))}
        </div>
      </main>
      {recipes && recipes.length > 0 && (
        <Link to="/new" className="btn primary fab">＋ New recipe</Link>
      )}
    </>
  );
}
