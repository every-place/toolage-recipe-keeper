import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, photoUrl, type Recipe } from "../api";

function useWakeLock() {
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null;
    const nav = navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> } };
    const get = () => nav.wakeLock?.request("screen").then((l) => (lock = l)).catch(() => {});
    get();
    const again = () => document.visibilityState === "visible" && get();
    document.addEventListener("visibilitychange", again);
    return () => {
      document.removeEventListener("visibilitychange", again);
      lock?.release().catch(() => {});
    };
  }, []);
}

function fmt(sec: number) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function beep() {
  try {
    const ctx = new AudioContext();
    for (let i = 0; i < 3; i++) {
      const o = ctx.createOscillator();
      o.frequency.value = 880;
      o.connect(ctx.destination);
      o.start(ctx.currentTime + i * 0.4);
      o.stop(ctx.currentTime + i * 0.4 + 0.2);
    }
  } catch {
    /* no audio */
  }
}

function Timer({ minutes }: { minutes: number }) {
  const total = Math.round(minutes * 60);
  const [endsAt, setEndsAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const beeped = useRef(false);
  useEffect(() => {
    if (!endsAt) return;
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [endsAt]);
  const left = endsAt ? Math.max(0, Math.round((endsAt - now) / 1000)) : total;
  const done = endsAt !== null && left === 0;
  useEffect(() => {
    if (done && !beeped.current) {
      beeped.current = true;
      beep();
      navigator.vibrate?.([300, 200, 300]);
    }
  }, [done]);
  return (
    <button
      className={`timer ${done ? "done" : ""}`}
      onClick={() => {
        beeped.current = false;
        setNow(Date.now());
        setEndsAt(endsAt && !done ? null : Date.now() + total * 1000);
      }}
    >
      ⏱ {done ? "Time's up!" : endsAt ? `${fmt(left)} · tap to stop` : `Start ${fmt(total)} timer`}
    </button>
  );
}

export default function CookMode() {
  const { id } = useParams();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [i, setI] = useState(0);
  const [got, setGot] = useState<Set<number>>(new Set());
  useWakeLock();

  useEffect(() => {
    api.getRecipe(Number(id)).then(setRecipe).catch(() => {});
  }, [id]);

  if (!recipe) return null;
  const steps = recipe.steps;
  const step = steps[i];
  const last = i === steps.length - 1;

  return (
    <div className="cook">
      <header className="topbar">
        <Link to={`/r/${recipe.id}`} className="icon-btn" aria-label="Leave cooking mode">✕</Link>
        <h1>{recipe.title}</h1>
      </header>
      <div className="step-count">Step {i + 1} of {steps.length}</div>
      <div className="step-text">{step?.text}</div>
      {step?.timer_minutes ? <div><Timer key={step.id} minutes={step.timer_minutes} /></div> : null}
      {step?.photo_id && <img className="step-img" src={photoUrl(step.photo_id)} alt="" />}
      <div className="spacer" />
      <details className="drawer">
        <summary>Ingredients ({recipe.ingredients.length - got.size} left)</summary>
        <ul className="check-list">
          {recipe.ingredients.map((ing, j) => (
            <li key={ing.id}>
              <label className={got.has(j) ? "got" : ""}>
                <input
                  type="checkbox"
                  checked={got.has(j)}
                  onChange={() => {
                    const next = new Set(got);
                    if (next.has(j)) next.delete(j);
                    else next.add(j);
                    setGot(next);
                  }}
                />
                {ing.raw_text}
              </label>
            </li>
          ))}
        </ul>
      </details>
      <div className="nav">
        <button className="btn" disabled={i === 0} onClick={() => setI(i - 1)}>← Back</button>
        {last ? (
          <Link className="btn primary" to={`/r/${recipe.id}`}>Done 🎉</Link>
        ) : (
          <button className="btn primary" onClick={() => setI(i + 1)}>Next →</button>
        )}
      </div>
    </div>
  );
}
