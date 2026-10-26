import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Ingredient, type RecipeInput, type Template } from "../api";
import AutoTextarea from "../components/AutoTextarea";
import PhotoPicker from "../components/PhotoPicker";
import { formatQuantity } from "../quantity";
import { BLANK, expandTemplate, fillFirstBlank, suggest } from "../templates";

type IngRow = { key: number; kind: "line" | "group"; text: string };
type StepRow = { key: number; text: string; photo_id: number | null; slots: string[] };

type Draft = Omit<RecipeInput, "ingredients" | "steps" | "tags"> & {
  tags: string;
  ingRows: IngRow[];
  stepRows: StepRow[];
};

let nextKey = 1;
const key = () => nextKey++;

const DEFAULT_CATEGORIES = ["Cookies", "Cakes", "Pies", "Breads", "Breakfast", "Main dishes", "Sides", "Soups", "Desserts", "Holidays"];
const QUICK_INSERTS = ["½", "⅓", "¼", "¾", "⅔", "cup", "tbsp", "tsp", "oz", "lb", "pinch", ", "];

function emptyDraft(): Draft {
  return {
    title: "", source_person: null, recipe_yield: null, servings: null, prep_minutes: null, cook_minutes: null,
    category: null, tags: "", story: null, story_year: null, notes: null, hero_photo_id: null, card_photo_id: null,
    ingRows: [{ key: key(), kind: "line", text: "" }],
    stepRows: [{ key: key(), text: "", photo_id: null, slots: [] }],
  };
}

function toInput(d: Draft): RecipeInput {
  const ingredients: RecipeInput["ingredients"] = [];
  let group: string | null = null;
  for (const row of d.ingRows) {
    if (row.kind === "group") group = row.text.trim() || null;
    else if (row.text.trim()) ingredients.push({ raw_text: row.text.trim(), group_label: group });
  }
  const { ingRows: _i, stepRows: _s, tags, ...rest } = d;
  return {
    ...rest,
    tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
    ingredients,
    steps: d.stepRows.filter((s) => s.text.trim() || s.photo_id).map((s) => ({ text: s.text.trim(), photo_id: s.photo_id })),
  };
}

function fromRecipe(r: RecipeInput & { ingredients: Ingredient[] }): Draft {
  const ingRows: IngRow[] = [];
  let group: string | null = null;
  for (const ing of r.ingredients) {
    if (ing.group_label && ing.group_label !== group) ingRows.push({ key: key(), kind: "group", text: ing.group_label });
    group = ing.group_label;
    ingRows.push({ key: key(), kind: "line", text: ing.raw_text });
  }
  ingRows.push({ key: key(), kind: "line", text: "" });
  const stepRows = r.steps.map((s) => ({ key: key(), text: s.text, photo_id: s.photo_id, slots: [] as string[] }));
  stepRows.push({ key: key(), text: "", photo_id: null, slots: [] });
  return { ...r, tags: r.tags.join(", "), ingRows, stepRows };
}

const num = (v: string) => (v.trim() === "" ? null : Number(v));

export default function Editor() {
  const { id } = useParams();
  const recipeId = id ? Number(id) : null;
  const navigate = useNavigate();
  const draftKey = `rk-draft-${recipeId ?? "new"}`;

  const [d, setD] = useState<Draft | null>(null);
  const [restored, setRestored] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [slots, setSlots] = useState<Record<string, string[]>>({});
  const [categories, setCategories] = useState<string[]>([]);
  const [parsed, setParsed] = useState<Record<string, Ingredient>>({});
  const [focusIng, setFocusIng] = useState<number | null>(null);
  const [focusStep, setFocusStep] = useState<number | null>(null);
  const [photoOpen, setPhotoOpen] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const ingRefs = useRef(new Map<number, HTMLInputElement>());
  const stepRefs = useRef(new Map<number, HTMLTextAreaElement>());
  const pendingFocus = useRef<{ kind: "ing" | "step"; key: number } | null>(null);

  // Load the recipe (or a saved draft) once.
  useEffect(() => {
    let saved: Draft | null = null;
    try {
      const raw = localStorage.getItem(draftKey);
      if (raw) saved = JSON.parse(raw);
    } catch {
      /* storage unavailable */
    }
    if (saved) {
      for (const r of saved.ingRows) nextKey = Math.max(nextKey, r.key + 1);
      for (const r of saved.stepRows) nextKey = Math.max(nextKey, r.key + 1);
      setD(saved);
      setRestored(true);
    } else if (recipeId) {
      api.getRecipe(recipeId).then((r) => setD(fromRecipe(r))).catch((e) => setError(e.message));
    } else {
      setD(emptyDraft());
    }
    api.templates().then((t) => { setTemplates(t.templates); setSlots(t.slots); }).catch(() => {});
    api.listRecipes().then((r) => setCategories(r.categories)).catch(() => {});
  }, [draftKey, recipeId]);

  // Keep a draft on the device so nothing is lost if the tablet goes to sleep.
  useEffect(() => {
    if (!d) return;
    const t = setTimeout(() => {
      try {
        localStorage.setItem(draftKey, JSON.stringify(d));
      } catch {
        /* storage full or unavailable */
      }
    }, 600);
    return () => clearTimeout(t);
  }, [d, draftKey]);

  // Read each ingredient line as it's typed and show what was understood.
  const lineTexts = useMemo(() => (d ? d.ingRows.filter((r) => r.kind === "line" && r.text.trim()).map((r) => r.text.trim()) : []), [d]);
  useEffect(() => {
    const missing = lineTexts.filter((t) => !parsed[t]);
    if (!missing.length) return;
    const t = setTimeout(() => {
      api.parseIngredients(missing.join("\n")).then(({ lines }) => {
        setParsed((p) => {
          const next = { ...p };
          for (const l of lines) next[l.raw_text] = l;
          return next;
        });
      }).catch(() => {});
    }, 500);
    return () => clearTimeout(t);
  }, [lineTexts, parsed]);

  useEffect(() => {
    const f = pendingFocus.current;
    if (!f) return;
    pendingFocus.current = null;
    (f.kind === "ing" ? ingRefs.current.get(f.key) : stepRefs.current.get(f.key))?.focus();
  });

  const allCategories = useMemo(() => Array.from(new Set([...categories, ...DEFAULT_CATEGORIES])), [categories]);

  if (error && !d) return <main className="page"><div className="error">{error}</div></main>;
  if (!d) return null;

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD({ ...d, [k]: v });
  const text = (k: keyof Draft) => (e: { target: { value: string } }) => set(k, (e.target.value || null) as never);

  // ---------- ingredients ----------
  const setIng = (rows: IngRow[]) => setD({ ...d, ingRows: rows });
  function ingKey(e: React.KeyboardEvent<HTMLInputElement>, i: number) {
    const rows = d!.ingRows;
    if (e.key === "Enter") {
      e.preventDefault();
      const row = { key: key(), kind: "line" as const, text: "" };
      setIng([...rows.slice(0, i + 1), row, ...rows.slice(i + 1)]);
      pendingFocus.current = { kind: "ing", key: row.key };
    } else if (e.key === "Backspace" && rows[i].text === "" && rows.length > 1) {
      e.preventDefault();
      setIng(rows.filter((_, j) => j !== i));
      pendingFocus.current = { kind: "ing", key: rows[Math.max(0, i - 1)].key };
    }
  }
  function ingPaste(e: React.ClipboardEvent<HTMLInputElement>, i: number) {
    const pasted = e.clipboardData.getData("text");
    if (!pasted.includes("\n")) return;
    e.preventDefault();
    const lines = pasted.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const rows = d!.ingRows;
    const newRows: IngRow[] = lines.map((l) =>
      l.endsWith(":") ? { key: key(), kind: "group", text: l.slice(0, -1) } : { key: key(), kind: "line", text: l }
    );
    const keep = rows[i].text.trim() ? [rows[i]] : [];
    setIng([...rows.slice(0, i), ...keep, ...newRows, ...rows.slice(i + 1)]);
  }
  function quickInsert(value: string) {
    if (focusIng === null) return;
    const el = ingRefs.current.get(focusIng);
    const i = d!.ingRows.findIndex((r) => r.key === focusIng);
    if (!el || i < 0) return;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? start;
    const before = el.value.slice(0, start);
    const pad = /^[a-z]/i.test(value) && before && !before.endsWith(" ") ? " " : "";
    const insert = pad + value + (/^[a-z]/i.test(value) ? " " : "");
    const next = before + insert + el.value.slice(end);
    const rows = [...d!.ingRows];
    rows[i] = { ...rows[i], text: next };
    setIng(rows);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + insert.length, start + insert.length);
    });
  }

  // ---------- steps ----------
  const setSteps = (rows: StepRow[]) => setD({ ...d, stepRows: rows });
  const updateStep = (i: number, patch: Partial<StepRow>) => {
    const rows = [...d.stepRows];
    rows[i] = { ...rows[i], ...patch };
    if (!rows[i].text.includes(BLANK)) rows[i].slots = [];
    // Always keep one empty step at the end to type into.
    if (i === rows.length - 1 && (rows[i].text || rows[i].photo_id)) rows.push({ key: key(), text: "", photo_id: null, slots: [] });
    setSteps(rows);
  };
  function stepKey(e: React.KeyboardEvent<HTMLTextAreaElement>, i: number) {
    const rows = d!.stepRows;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const next = rows[i + 1];
      if (next && !next.text) {
        pendingFocus.current = { kind: "step", key: next.key };
        setSteps([...rows]);
      } else {
        const row = { key: key(), text: "", photo_id: null, slots: [] };
        setSteps([...rows.slice(0, i + 1), row, ...rows.slice(i + 1)]);
        pendingFocus.current = { kind: "step", key: row.key };
      }
    } else if (e.key === "Backspace" && rows[i].text === "" && !rows[i].photo_id && rows.length > 1 && i > 0) {
      e.preventDefault();
      setSteps(rows.filter((_, j) => j !== i));
      pendingFocus.current = { kind: "step", key: rows[i - 1].key };
    }
  }
  function applyTemplate(i: number, tpl: Template) {
    const { text: t, slots: s } = expandTemplate(tpl.text);
    updateStep(i, { text: t, slots: s });
    const el = stepRefs.current.get(d!.stepRows[i].key);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const at = t.indexOf(BLANK);
      if (at >= 0) el.setSelectionRange(at, at + BLANK.length);
    });
  }
  function fillSlot(i: number, value: string) {
    const row = d!.stepRows[i];
    updateStep(i, { text: fillFirstBlank(row.text, value), slots: row.slots.slice(1) });
    const el = stepRefs.current.get(row.key);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const at = el.value.indexOf(BLANK);
      if (at >= 0) el.setSelectionRange(at, at + BLANK.length);
    });
  }
  function moveStep(i: number, dir: -1 | 1) {
    const rows = [...d!.stepRows];
    const j = i + dir;
    if (j < 0 || j >= rows.length) return;
    [rows[i], rows[j]] = [rows[j], rows[i]];
    setSteps(rows);
  }

  // ---------- save ----------
  async function save() {
    if (!d!.title.trim()) {
      setError("Give the recipe a title first.");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const blank = d!.stepRows.findIndex((s) => s.text.includes(BLANK));
    if (blank >= 0) {
      setError(`Step ${blank + 1} still has a blank (___) to fill in.`);
      stepRefs.current.get(d!.stepRows[blank].key)?.focus();
      return;
    }
    setSaving(true);
    setError("");
    try {
      const body = toInput(d!);
      const saved = recipeId ? await api.updateRecipe(recipeId, body) : await api.createRecipe(body);
      try { localStorage.removeItem(draftKey); } catch { /* ignore */ }
      navigate(`/r/${saved.id}`, { replace: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  function discardDraft() {
    try { localStorage.removeItem(draftKey); } catch { /* ignore */ }
    setRestored(false);
    if (recipeId) api.getRecipe(recipeId).then((r) => setD(fromRecipe(r)));
    else setD(emptyDraft());
  }

  const ingredientNames = Array.from(new Set(
    d.ingRows.filter((r) => r.kind === "line").map((r) => parsed[r.text.trim()]?.name).filter((n): n is string => !!n)
  ));
  let lineNo = 0;

  return (
    <>
      <header className="topbar">
        <Link to={recipeId ? `/r/${recipeId}` : "/"} className="icon-btn" aria-label="Close">✕</Link>
        <h1>{recipeId ? "Edit recipe" : "New recipe"}</h1>
      </header>
      <main className="page narrow">
        {restored && (
          <div className="card" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ flex: 1 }}>We kept your unsaved changes from last time.</span>
            <button className="btn small" onClick={discardDraft}>Start over</button>
          </div>
        )}
        {error && <div className="error">{error}</div>}

        <div className="card index-card editor-section">
          <input className="title-input" placeholder="Recipe name" value={d.title} onChange={(e) => set("title", e.target.value)} autoFocus={!recipeId} />
          <input className="from-input" placeholder="from… (Grandma Ruth, Mom, my own)" value={d.source_person ?? ""} onChange={text("source_person")} />
        </div>

        <div className="editor-section">
          <PhotoPicker photoId={d.hero_photo_id} onChange={(v) => set("hero_photo_id", v)} label="Add a photo of the finished dish" />
        </div>

        <div className="card editor-section">
          <h2>Ingredients</h2>
          <p className="hint">One per line, like on a card: <i>1/2 cup flour, sifted</i>. Press Enter for the next line. End a line with “:” to start a group.</p>
          {d.ingRows.map((row, i) => {
            if (row.kind === "line" && row.text.trim()) lineNo++;
            const p = row.kind === "line" ? parsed[row.text.trim()] : undefined;
            return (
              <div key={row.key}>
                <div className="line-row">
                  <span className="num">{row.kind === "group" ? "§" : "•"}</span>
                  <input
                    ref={(el) => { if (el) ingRefs.current.set(row.key, el); else ingRefs.current.delete(row.key); }}
                    className={`input ${row.kind === "group" ? "group-input" : ""}`}
                    value={row.text}
                    placeholder={row.kind === "group" ? "Group name, e.g. For the frosting" : i === 0 ? "3 eggs" : "Next ingredient"}
                    enterKeyHint="next"
                    onFocus={() => setFocusIng(row.key)}
                    onBlur={() => setTimeout(() => setFocusIng((k) => (k === row.key ? null : k)), 150)}
                    onKeyDown={(e) => ingKey(e, i)}
                    onPaste={(e) => ingPaste(e, i)}
                    onChange={(e) => {
                      const v = e.target.value;
                      const rows = [...d.ingRows];
                      rows[i] = v.endsWith(":") && row.kind === "line" && !/\d/.test(v)
                        ? { ...row, kind: "group", text: v.slice(0, -1) }
                        : { ...row, text: v };
                      if (i === rows.length - 1 && v) rows.push({ key: key(), kind: "line", text: "" });
                      setIng(rows);
                    }}
                  />
                </div>
                {focusIng === row.key && row.kind === "line" && (
                  <div className="fraction-bar" onMouseDown={(e) => e.preventDefault()}>
                    {QUICK_INSERTS.map((q) => (
                      <button key={q} type="button" onClick={() => quickInsert(q)}>{q === ", " ? "," : q}</button>
                    ))}
                  </div>
                )}
                {p && p.name && (p.quantity != null || p.unit || p.note) && (
                  <div className="parsed" aria-label="How this line was read">
                    {p.quantity != null && <span>{formatQuantity(p.quantity)}{p.quantity_max != null ? `–${formatQuantity(p.quantity_max)}` : ""}</span>}
                    {p.unit && <span>{p.unit}</span>}
                    <span>{p.name}</span>
                    {p.note && <span className="note">{p.note}</span>}
                  </div>
                )}
              </div>
            );
          })}
          <button className="btn small quiet" onClick={() => setIng([...d.ingRows, { key: key(), kind: "group", text: "" }, { key: key(), kind: "line", text: "" }])}>
            ＋ Add a group
          </button>
        </div>

        <div className="card editor-section">
          <h2>Steps</h2>
          <p className="hint">Start typing and pick a suggestion, or write it your own way. Tap the blanks to fill them in.</p>
          {d.stepRows.map((row, i) => {
            const focused = focusStep === row.key;
            const sugg = focused && !row.text.includes(BLANK) ? suggest(row.text, templates) : [];
            const slot = row.slots[0];
            const isLast = i === d.stepRows.length - 1;
            return (
              <div key={row.key}>
                <div className="line-row">
                  <span className="num">{i + 1}</span>
                  <AutoTextarea
                    ref={(el) => { if (el) stepRefs.current.set(row.key, el); else stepRefs.current.delete(row.key); }}
                    className="input"
                    value={row.text}
                    placeholder={i === 0 ? "Try typing “pre”…" : "Next step"}
                    enterKeyHint="next"
                    onFocus={() => setFocusStep(row.key)}
                    onBlur={() => setTimeout(() => setFocusStep((k) => (k === row.key ? null : k)), 200)}
                    onKeyDown={(e) => stepKey(e, i)}
                    onChange={(e) => updateStep(i, { text: e.target.value })}
                  />
                  {!isLast && (
                    <span style={{ display: "flex", flexDirection: "column" }} className="no-print">
                      <button className="icon-btn" style={{ height: 24, fontSize: 14 }} aria-label="Move step up" onClick={() => moveStep(i, -1)}>▲</button>
                      <button className="icon-btn" style={{ height: 24, fontSize: 14 }} aria-label="Move step down" onClick={() => moveStep(i, 1)}>▼</button>
                    </span>
                  )}
                </div>
                {sugg.length > 0 && (
                  <div className="suggestions" onMouseDown={(e) => e.preventDefault()}>
                    {sugg.map((tpl) => (
                      <button key={tpl.text} type="button" className="suggestion" onClick={() => applyTemplate(i, tpl)}>
                        {tpl.text.split(/(\{\w+\})/).map((part, j) =>
                          part.startsWith("{") ? <span key={j} className="slot">{part.slice(1, -1)}</span> : part
                        )}
                      </button>
                    ))}
                  </div>
                )}
                {slot && row.text.includes(BLANK) && (
                  <div className="slot-help" onMouseDown={(e) => e.preventDefault()}>
                    <div className="label">Fill in: {slot}</div>
                    <div className="chips" style={{ marginBottom: 0 }}>
                      {(slot.startsWith("ingredient") ? ingredientNames : slots[slot] || []).map((v) => (
                        <button key={v} type="button" className="chip" onClick={() => fillSlot(i, v)}>{v}</button>
                      ))}
                      <button type="button" className="chip" onClick={() => {
                        const el = stepRefs.current.get(row.key);
                        const at = row.text.indexOf(BLANK);
                        el?.focus();
                        el?.setSelectionRange(at, at + BLANK.length);
                      }}>Type my own</button>
                    </div>
                  </div>
                )}
                {!isLast && (
                  <div className="step-photo">
                    {row.photo_id || photoOpen === row.key ? (
                      <div style={{ maxWidth: 260 }}>
                        <PhotoPicker small photoId={row.photo_id} onChange={(v) => { updateStep(i, { photo_id: v }); setPhotoOpen(null); }} label="Add a photo of this step" />
                      </div>
                    ) : (
                      <button type="button" className="btn small quiet" style={{ color: "var(--ink-soft)" }} onClick={() => setPhotoOpen(row.key)}>
                        📷 Add step photo
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="card editor-section">
          <h2>The story behind it</h2>
          <p className="hint">Who taught you this? When do you make it? What do you remember?</p>
          <AutoTextarea className="input story" style={{ fontSize: 22 }} value={d.story ?? ""} onChange={text("story")} placeholder="Every Christmas Eve, Grandma and I…" />
          <div className="row" style={{ marginTop: 12 }}>
            <label className="field">
              <span>Year or occasion</span>
              <input className="input" value={d.story_year ?? ""} onChange={text("story_year")} placeholder="1985, or Christmas" />
            </label>
          </div>
          <PhotoPicker small photoId={d.card_photo_id} onChange={(v) => set("card_photo_id", v)} label="Snap the original handwritten card" />
        </div>

        <div className="card editor-section">
          <h2>Details</h2>
          <div className="row">
            <label className="field">
              <span>Makes</span>
              <input className="input" value={d.recipe_yield ?? ""} onChange={text("recipe_yield")} placeholder="3 dozen cookies" />
            </label>
            <label className="field">
              <span>Servings</span>
              <input className="input" inputMode="decimal" value={d.servings ?? ""} onChange={(e) => set("servings", num(e.target.value))} />
            </label>
          </div>
          <div className="row">
            <label className="field">
              <span>Prep (minutes)</span>
              <input className="input" inputMode="numeric" value={d.prep_minutes ?? ""} onChange={(e) => set("prep_minutes", num(e.target.value))} />
            </label>
            <label className="field">
              <span>Cook (minutes)</span>
              <input className="input" inputMode="numeric" value={d.cook_minutes ?? ""} onChange={(e) => set("cook_minutes", num(e.target.value))} />
            </label>
          </div>
          <label className="field">
            <span>Category</span>
            <input className="input" list="categories" value={d.category ?? ""} onChange={text("category")} placeholder="Cookies" />
            <datalist id="categories">{allCategories.map((c) => <option key={c} value={c} />)}</datalist>
          </label>
          <label className="field">
            <span>Tags (separate with commas)</span>
            <input className="input" value={d.tags} onChange={(e) => set("tags", e.target.value)} placeholder="Christmas, gluten-free" />
          </label>
          <label className="field" style={{ marginBottom: 0 }}>
            <span>Notes and tips</span>
            <AutoTextarea className="input" value={d.notes ?? ""} onChange={text("notes")} placeholder="Chill the dough overnight for the best shape." />
          </label>
        </div>
      </main>
      <div className="save-bar">
        <span className="status" style={error ? { color: "var(--accent)" } : undefined}>{error ? error : <>{lineNo} ingredient{lineNo === 1 ? "" : "s"} · {d.stepRows.filter((s) => s.text.trim()).length} steps</>}</span>
        <button className="btn primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save recipe"}</button>
      </div>
    </>
  );
}
