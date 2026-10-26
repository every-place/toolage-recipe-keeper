import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, nutritionApi, type FoodResult, type Nutrition, type NutritionLine } from "../api";
import { useSession } from "../session";

const ROWS: [keyof Nutrition["total"], string, string][] = [
  ["fat_g", "Fat", "g"],
  ["carbs_g", "Carbohydrates", "g"],
  ["sugar_g", "Sugars", "g"],
  ["fiber_g", "Fiber", "g"],
  ["protein_g", "Protein", "g"],
  ["sodium_mg", "Sodium", "mg"],
];

const STATUS_TEXT: Record<NutritionLine["status"], string> = {
  ok: "",
  unmatched: "No match yet",
  skipped: "Not counted",
  no_amount: "No amount, not counted",
  no_conversion: "Can't convert this amount",
};

function MatchEditor({ line, onDone }: { line: NutritionLine; onDone: () => void }) {
  const [q, setQ] = useState(line.name || "");
  const [results, setResults] = useState<FoodResult[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const search = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      setResults((await nutritionApi.search(text)).results);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    search(line.name || "");
  }, [line.name, search]);

  async function choose(foodId: string | null, skip = false) {
    setBusy(true);
    try {
      await nutritionApi.choose(line.name || line.raw_text, foodId, skip);
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="match-editor">
      <form className="row" onSubmit={(e) => { e.preventDefault(); search(q); }}>
        <input className="input" style={{ flex: "3 1 160px" }} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search foods" />
        <button className="btn small" disabled={busy}>Search</button>
      </form>
      {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      <ul className="list-plain">
        {results?.map((r) => (
          <li key={r.food_id}>
            <button className="food-choice" disabled={busy} onClick={() => choose(r.food_id)}>
              <b>{r.name}</b>{r.brand ? ` (${r.brand})` : ""}
              <span className="hint">{r.summary}</span>
            </button>
          </li>
        ))}
        {results && results.length === 0 && <li className="hint">Nothing found. Try a simpler word.</li>}
      </ul>
      <button className="btn small quiet" disabled={busy} onClick={() => choose(null, true)}>Don't count this ingredient</button>
    </div>
  );
}

export default function NutritionPanel({ recipeId }: { recipeId: number }) {
  const { me } = useSession();
  const premium = me.household.plan === "premium";
  const [data, setData] = useState<Nutrition | null>(null);
  const [state, setState] = useState<"loading" | "matching" | "ready" | "error" | "off">("loading");
  const [message, setMessage] = useState("");
  const [whole, setWhole] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const triedMatch = useRef(false);

  const load = useCallback(async () => {
    try {
      let n = await nutritionApi.get(recipeId);
      setData(n);
      setState("ready");
      if (n.lines.some((l) => l.status === "unmatched") && !triedMatch.current) {
        triedMatch.current = true;
        setState("matching");
        n = await nutritionApi.match(recipeId);
        setData(n);
        setState("ready");
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setState("off");
      else {
        setMessage((e as Error).message);
        setState(data ? "ready" : "error");
      }
    }
  }, [recipeId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (premium) load();
  }, [premium, load]);

  if (!premium) {
    return (
      <div className="card nutrition upsell no-print">
        <h3 className="section-title">Nutrition facts</h3>
        <p style={{ margin: 0 }}>
          See calories, fat, carbs, sugar and protein for every recipe, worked out from the ingredients as you type them.
        </p>
        <p className="hint" style={{ marginBottom: 0 }}>Part of Recipe Keeper Premium.</p>
      </div>
    );
  }
  if (state === "off") return null;

  const perServing = !whole && data?.per_serving;
  const n = data ? (perServing ? data.per_serving! : data.total) : null;
  const totalLines = data?.lines.length ?? 0;

  return (
    <div className="card nutrition">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <h3 className="section-title">Nutrition facts</h3>
        {data?.per_serving && (
          <div className="scaler no-print" role="group" aria-label="Show nutrition for">
            <button className={!whole ? "on" : ""} onClick={() => setWhole(false)}>Per serving</button>
            <button className={whole ? "on" : ""} onClick={() => setWhole(true)}>Whole recipe</button>
          </div>
        )}
      </div>
      {state === "loading" && <p className="hint">Loading…</p>}
      {state === "matching" && !data?.counted && <p className="hint">Looking up the ingredients…</p>}
      {state === "error" && <div className="error">{message}</div>}
      {n && data && data.counted > 0 && (
        <div className="label">
          <div className="label-cal">
            <span>Calories</span>
            <b>{Math.round(n.calories)}</b>
          </div>
          {ROWS.map(([k, label, unit]) => (
            <div key={k} className="label-row">
              <span>{label}</span>
              <span>{Math.round(n[k])} {unit}</span>
            </div>
          ))}
          <div className="hint" style={{ marginTop: 6 }}>
            {perServing ? `Per serving, ${data.servings} servings. ` : "Whole recipe. "}
            Raw ingredients; cooking isn't taken into account.
          </div>
        </div>
      )}
      {data && data.counted === 0 && state === "ready" && (
        <p className="hint">None of the ingredients could be counted yet. Check the matches below.</p>
      )}
      {data && !data.servings && data.counted > 0 && (
        <p className="hint">Add the number of servings to see per-serving numbers.</p>
      )}
      {message && state === "ready" && <div className="error">{message}</div>}

      {data && (
        <details className="no-print" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
          <summary className="hint" style={{ cursor: "pointer", minHeight: 44, display: "flex", alignItems: "center" }}>
            Based on {data.counted} of {totalLines} ingredients{data.needs_attention ? ` · ${data.needs_attention} to check` : ""}
          </summary>
          <ul className="list-plain match-list">
            {data.lines.map((l, i) => (
              <li key={l.ingredient_id ?? i} style={{ display: "block" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ flex: 1 }}>
                    {l.raw_text}
                    <br />
                    <span className={`match-chip ${l.status}`}>
                      {l.food_name && l.status !== "skipped" ? `→ ${l.food_name}` : ""}
                      {STATUS_TEXT[l.status] ? `${l.food_name && l.status !== "skipped" ? " · " : ""}${STATUS_TEXT[l.status]}` : ""}
                      {l.status === "ok" && l.nutrients ? ` · ${Math.round(l.nutrients.calories)} cal` : ""}
                    </span>
                  </span>
                  {l.name && l.status !== "no_amount" && (
                    <button className="btn small quiet" onClick={() => setEditing(editing === i ? null : i)}>
                      {editing === i ? "Close" : "Change"}
                    </button>
                  )}
                </div>
                {editing === i && (
                  <MatchEditor
                    line={l}
                    onDone={() => {
                      setEditing(null);
                      load();
                    }}
                  />
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="hint" style={{ marginBottom: 0, fontSize: 12 }}>
        <a href="https://www.fatsecret.com" target="_blank" rel="noreferrer">Powered by FatSecret</a>
      </p>
    </div>
  );
}
