import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, menuApi, photoUrl, type Menu, type RecipeSummary, type ShopItem, type Shopping } from "../api";

const BATCHES = [0.5, 1, 2, 3];

function SendBar({ shopping }: { shopping: Shopping }) {
  const [copied, setCopied] = useState(false);
  const text = shopping.text;
  const subject = `Shopping list: ${shopping.menu.name}`;
  const canShare = typeof navigator !== "undefined" && "share" in navigator;
  return (
    <div className="send-bar">
      {canShare && (
        <button className="btn primary small" onClick={() => navigator.share({ title: subject, text }).catch(() => {})}>
          Send…
        </button>
      )}
      <a className="btn small" href={`sms:?&body=${encodeURIComponent(text)}`}>Text it</a>
      <a className="btn small" href={`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`}>Email it</a>
      <button
        className="btn small"
        onClick={() =>
          navigator.clipboard?.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          })
        }
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function Item({ item, onState, onStaple }: { item: ShopItem; onState: (s: ShopItem["state"] | null) => void; onStaple: (on: boolean) => void }) {
  const got = item.state === "got";
  if (item.state === "have") {
    return (
      <li className="shop-item have">
        <span style={{ flex: 1 }}>
          {item.name}
          {item.amount && <span className="hint"> · {item.amount}</span>}
        </span>
        <button className={`star ${item.staple ? "on" : ""}`} aria-pressed={item.staple} title="Usually have this" onClick={() => onStaple(!item.staple)}>
          {item.staple ? "★" : "☆"}
        </button>
        <button className="btn small" onClick={() => onState("need")}>Need it</button>
      </li>
    );
  }
  return (
    <li className={`shop-item ${got ? "got" : ""}`}>
      <label style={{ flex: 1 }}>
        <input type="checkbox" checked={got} onChange={() => onState(got ? "need" : "got")} />
        <span>
          <span className="shop-name">{item.name}</span>
          {item.amount && <span className="shop-amount"> {item.amount}</span>}
          <br />
          <span className="hint" style={{ fontSize: 13 }}>{item.recipes.join(", ")}</span>
        </span>
      </label>
      {!got && <button className="btn small quiet" onClick={() => onState("have")}>Have it</button>}
    </li>
  );
}

export default function MenuPage() {
  const { id } = useParams();
  const menuId = Number(id);
  const navigate = useNavigate();
  const [tab, setTab] = useState<"recipes" | "list">("recipes");
  const [menu, setMenu] = useState<Menu | null>(null);
  const [shopping, setShopping] = useState<Shopping | null>(null);
  const [picking, setPicking] = useState(false);
  const [box, setBox] = useState<RecipeSummary[]>([]);
  const [error, setError] = useState("");
  const [showHave, setShowHave] = useState(false);

  useEffect(() => {
    menuApi.get(menuId).then((m) => {
      setMenu(m);
      if (m.recipes.length) setTab("list");
    }).catch((e) => setError(e.message));
  }, [menuId]);

  const loadList = useCallback(() => menuApi.shopping(menuId).then(setShopping).catch(() => {}), [menuId]);

  // Keep the list in sync with family members shopping at the same time.
  useEffect(() => {
    if (tab !== "list") return;
    loadList();
    const t = setInterval(() => document.visibilityState === "visible" && loadList(), 15000);
    return () => clearInterval(t);
  }, [tab, loadList]);

  async function openPicker() {
    setPicking(true);
    setBox((await api.listRecipes()).recipes);
  }

  async function toggleRecipe(recipeId: number, inMenu: boolean) {
    setMenu(await menuApi.setRecipe(menuId, recipeId, inMenu ? 0 : 1));
  }

  async function setState(item: ShopItem, state: ShopItem["state"] | null) {
    // Show the tick at once; the server answer follows.
    setShopping((s) => s && { ...s, aisles: s.aisles.map((g) => ({ ...g, items: g.items.map((i) => (i.key === item.key && state ? { ...i, state } : i)) })) });
    setShopping(await menuApi.check(menuId, item.key, state));
  }

  async function setStaple(item: ShopItem, on: boolean) {
    await menuApi.staple(item.name, on);
    loadList();
  }

  async function removeMenu() {
    if (!menu || !confirm(`Delete the menu "${menu.name}"? Your recipes stay in the box.`)) return;
    await menuApi.remove(menuId);
    navigate("/menus");
  }

  if (error) return <main className="page"><div className="error">{error}</div><Link className="btn" to="/menus">Back</Link></main>;
  if (!menu) return null;
  const inMenu = new Set(menu.recipes.map((r) => r.recipe_id));
  const have = shopping?.aisles.flatMap((g) => g.items.filter((i) => i.state === "have")) ?? [];

  return (
    <>
      <header className="topbar">
        <Link to="/menus" className="icon-btn" aria-label="Back to menus">←</Link>
        <h1>{menu.name}</h1>
      </header>
      <main className="page narrow">
        <div className="tabs">
          <button className={tab === "recipes" ? "on" : ""} onClick={() => setTab("recipes")}>Recipes ({menu.recipes.length})</button>
          <button className={tab === "list" ? "on" : ""} onClick={() => setTab("list")}>Shopping list</button>
        </div>

        {tab === "recipes" && (
          <>
            <ul className="list-plain">
              {menu.recipes.map((r) => (
                <li key={r.recipe_id} style={{ flexWrap: "wrap" }}>
                  <div className="thumb" style={r.hero_photo_id ? { backgroundImage: `url(${photoUrl(r.hero_photo_id)})` } : undefined} />
                  <Link to={`/r/${r.recipe_id}`} style={{ flex: 1, minWidth: 120 }}>{r.title}</Link>
                  <div className="scaler" role="group" aria-label={`Batches of ${r.title}`}>
                    {BATCHES.map((b) => (
                      <button key={b} className={r.multiplier === b ? "on" : ""} onClick={() => menuApi.setRecipe(menuId, r.recipe_id, b).then(setMenu)}>
                        {b === 0.5 ? "½×" : `${b}×`}
                      </button>
                    ))}
                  </div>
                  <button className="icon-btn" aria-label={`Remove ${r.title}`} onClick={() => toggleRecipe(r.recipe_id, true)}>✕</button>
                </li>
              ))}
            </ul>
            {!picking && <button className="btn primary" style={{ marginTop: 12 }} onClick={openPicker}>＋ Add recipes</button>}
            {picking && (
              <div className="card" style={{ marginTop: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 className="section-title" style={{ margin: 0 }}>Pick from your box</h3>
                  <button className="btn small" onClick={() => setPicking(false)}>Done</button>
                </div>
                <ul className="check-list">
                  {box.map((r) => (
                    <li key={r.id}>
                      <label>
                        <input type="checkbox" checked={inMenu.has(r.id)} onChange={() => toggleRecipe(r.id, inMenu.has(r.id))} />
                        {r.title}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p style={{ marginTop: 32 }}>
              <button className="btn quiet small danger" onClick={removeMenu}>Delete this menu</button>
            </p>
          </>
        )}

        {tab === "list" && shopping && (
          <>
            {menu.recipes.length === 0 ? (
              <p className="hint">Add some recipes first, and their ingredients show up here.</p>
            ) : (
              <>
                <p className="hint" style={{ marginTop: 0 }}>
                  Tick off what's in the kitchen with “Have it” before you go, then tick items as they go in the cart.
                </p>
                <SendBar shopping={shopping} />
                {shopping.aisles.map((g) => {
                  const items = g.items.filter((i) => i.state !== "have");
                  if (!items.length) return null;
                  return (
                    <div key={g.aisle} className="card shop-aisle">
                      <h3 className="aisle-title">{g.aisle}</h3>
                      <ul className="list-plain">
                        {items.map((i) => (
                          <Item key={i.key} item={i} onState={(s) => setState(i, s)} onStaple={(on) => setStaple(i, on)} />
                        ))}
                      </ul>
                    </div>
                  );
                })}
                {shopping.counts.need === 0 && shopping.counts.got > 0 && <p className="empty">All done. Happy baking!</p>}
                {have.length > 0 && (
                  <div className="card">
                    <button className="btn quiet small" onClick={() => setShowHave(!showHave)}>
                      {showHave ? "▾" : "▸"} Already have ({have.length})
                    </button>
                    {showHave && (
                      <>
                        <p className="hint">★ marks things you usually have, so they start here on every list.</p>
                        <ul className="list-plain">
                          {have.map((i) => (
                            <Item key={i.key} item={i} onState={(s) => setState(i, s)} onStaple={(on) => setStaple(i, on)} />
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
                <button className="btn quiet small" onClick={() => menuApi.reset(menuId).then(setShopping)}>Start the list over</button>
              </>
            )}
          </>
        )}
      </main>
    </>
  );
}
