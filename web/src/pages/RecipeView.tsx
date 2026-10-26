import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, menuApi, photoUrl, type MenuSummary, type Recipe } from "../api";
import { scaleLine } from "../quantity";
import NutritionPanel from "../components/NutritionPanel";

const SCALES = [0.5, 1, 2, 3];

export function minutesLabel(m: number | null) {
  if (!m) return "";
  const h = Math.floor(m / 60);
  const r = m % 60;
  return [h ? `${h} hr` : "", r ? `${r} min` : ""].filter(Boolean).join(" ");
}

export default function RecipeView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [error, setError] = useState("");
  const [scale, setScale] = useState(1);
  const [menus, setMenus] = useState<MenuSummary[] | null>(null);
  const [added, setAdded] = useState("");

  useEffect(() => {
    if (!added) return;
    const t = setTimeout(() => setAdded(""), 4000);
    return () => clearTimeout(t);
  }, [added]);

  useEffect(() => {
    api.getRecipe(Number(id)).then(setRecipe).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <main className="page"><div className="error">{error}</div><Link to="/" className="btn">Back to the box</Link></main>;
  if (!recipe) return null;

  async function remove() {
    if (!recipe || !confirm(`Delete "${recipe.title}"? This can't be undone.`)) return;
    await api.deleteRecipe(recipe.id);
    navigate("/");
  }

  let group: string | null = null;
  const yieldText = recipe.recipe_yield || (recipe.servings ? `${recipe.servings} servings` : "");

  return (
    <>
      <header className="topbar">
        <Link to="/" className="icon-btn" aria-label="Back to the recipe box">←</Link>
        <h1>{recipe.title}</h1>
        <Link to={`/r/${recipe.id}/edit`} className="btn small">Edit</Link>
      </header>
      <main className="page">
        {recipe.hero_photo_id && <img className="hero" src={photoUrl(recipe.hero_photo_id)} alt="" />}
        <div className="card index-card">
          <h2 className="recipe-title">{recipe.title}</h2>
          {recipe.source_person && (
            <div className="from-line">from {recipe.source_person}{recipe.story_year ? `, ${recipe.story_year}` : ""}</div>
          )}
          <div className="meta">
            {yieldText && <span>Makes <b>{yieldText}</b></span>}
            {recipe.prep_minutes ? <span>Prep <b>{minutesLabel(recipe.prep_minutes)}</b></span> : null}
            {recipe.cook_minutes ? <span>Cook <b>{minutesLabel(recipe.cook_minutes)}</b></span> : null}
            {recipe.category && <span>{recipe.category}</span>}
          </div>
          {recipe.tags.length > 0 && (
            <div className="tags">{recipe.tags.map((t) => <span key={t} className="tag">{t}</span>)}</div>
          )}
        </div>

        <div className="actions">
          {recipe.steps.length > 0 && <Link to={`/r/${recipe.id}/cook`} className="btn primary">▶ Start cooking</Link>}
          <button className="btn" onClick={() => menuApi.list().then((d) => setMenus(d.menus))}>🛒 Add to menu</button>
          <button className="btn" onClick={() => window.print()}>Print card</button>
          <a className="btn" href={`/api/recipes/${recipe.id}/schema.json`} download={`${recipe.title}.json`}>Export</a>
        </div>

        {recipe.story && (
          <div className="card">
            <h3 className="section-title">The story</h3>
            <div className="story">{recipe.story}</div>
          </div>
        )}

        <div className="two-col">
          <div className="card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <h3 className="section-title">Ingredients</h3>
              <div className="scaler no-print" role="group" aria-label="Batch size">
                {SCALES.map((s) => (
                  <button key={s} className={s === scale ? "on" : ""} onClick={() => setScale(s)}>
                    {s === 0.5 ? "½×" : `${s}×`}
                  </button>
                ))}
              </div>
            </div>
            <ul className="ingredients">
              {recipe.ingredients.map((ing) => {
                const header = ing.group_label && ing.group_label !== group ? ing.group_label : null;
                group = ing.group_label;
                return (
                  <li key={ing.id} style={{ display: "block" }}>
                    {header && <div className="group" style={{ fontWeight: 600, color: "var(--ink-soft)" }}>{header}</div>}
                    {scaleLine(ing, scale)}
                  </li>
                );
              })}
              {recipe.ingredients.length === 0 && <li className="hint">No ingredients yet.</li>}
            </ul>
          </div>
          <div className="card">
            <h3 className="section-title">Steps</h3>
            <ol className="steps">
              {recipe.steps.map((s) => (
                <li key={s.id}>
                  <span>{s.text}</span>
                  {s.photo_id && <img src={photoUrl(s.photo_id)} alt="" />}
                </li>
              ))}
            </ol>
            {recipe.steps.length === 0 && <p className="hint">No steps yet.</p>}
          </div>
        </div>

        {recipe.ingredients.length > 0 && <NutritionPanel recipeId={recipe.id} />}

        {recipe.notes && (
          <div className="card">
            <h3 className="section-title">Notes and tips</h3>
            <div style={{ whiteSpace: "pre-wrap" }}>{recipe.notes}</div>
          </div>
        )}
        {recipe.card_photo_id && (
          <div className="card no-print">
            <h3 className="section-title">The original card</h3>
            <img className="card-photo" src={photoUrl(recipe.card_photo_id)} alt="The original handwritten recipe card" />
          </div>
        )}
        {menus && (
          <div className="sheet" onClick={() => setMenus(null)}>
            <div onClick={(e) => e.stopPropagation()}>
              <h3 className="section-title">Add to which menu?</h3>
              <ul className="list-plain">
                {menus.map((m) => (
                  <li key={m.id}>
                    <button
                      className="btn quiet"
                      style={{ flex: 1, justifyContent: "flex-start" }}
                      onClick={async () => {
                        await menuApi.setRecipe(m.id, recipe.id, scale);
                        setMenus(null);
                        setAdded(m.name);
                      }}
                    >
                      {m.name}
                    </button>
                  </li>
                ))}
              </ul>
              <button
                className="btn primary"
                style={{ marginTop: 12, width: "100%" }}
                onClick={async () => {
                  const m = await menuApi.create("This week");
                  await menuApi.setRecipe(m.id, recipe.id, scale);
                  setMenus(null);
                  setAdded(m.name);
                }}
              >
                ＋ New menu “This week”
              </button>
            </div>
          </div>
        )}
        {added && (
          <div className="toast" onClick={() => navigate("/menus")}>
            Added to {added} · <u>Open menus</u>
          </div>
        )}
        <p className="hint no-print">
          {recipe.created_by_name ? `Added by ${recipe.created_by_name}. ` : ""}
          <button className="btn quiet small danger" onClick={remove}>Delete recipe</button>
        </p>
      </main>
    </>
  );
}
