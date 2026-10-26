import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Template } from "../api";
import { useSession } from "../session";

export default function Settings() {
  const { me, refresh } = useSession();
  const [mine, setMine] = useState<Template[]>([]);
  const [newTpl, setNewTpl] = useState("");
  const [toast, setToast] = useState("");

  const load = () => api.templates().then((t) => setMine(t.templates.filter((x) => x.custom)));
  useEffect(() => {
    load();
  }, []);

  async function add() {
    if (!newTpl.trim()) return;
    await api.addTemplate(newTpl.trim());
    setNewTpl("");
    load();
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(me.household.join_code);
      setToast("Family code copied");
      setTimeout(() => setToast(""), 2000);
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <>
      <header className="topbar">
        <Link to="/" className="icon-btn" aria-label="Back">←</Link>
        <h1>Settings</h1>
      </header>
      <main className="page narrow">
        <div className="card">
          <h2 style={{ fontSize: 22, marginBottom: 6 }}>{me.household.name}</h2>
          <span className="plan-badge">{me.household.plan === "premium" ? "Premium" : "Free plan"}</span>
          <h3 style={{ fontSize: 17, margin: "18px 0 6px" }}>Invite your family</h3>
          <p className="hint" style={{ marginTop: 0 }}>
            Share this code. When they create an account, they choose “Join my family's” and type it in.
          </p>
          <button className="code" style={{ border: "none", cursor: "pointer" }} onClick={copyCode}>{me.household.join_code}</button>
          <h3 style={{ fontSize: 17, margin: "18px 0 6px" }}>Who's here</h3>
          <ul className="list-plain">
            {me.household.members.map((m) => (
              <li key={m.id}><span>{m.display_name}</span><span className="hint">{m.email}</span></li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2 style={{ fontSize: 22, marginBottom: 6 }}>Your own step phrases</h2>
          <p className="hint" style={{ marginTop: 0 }}>
            Phrases you use a lot show up as suggestions when writing steps. Put a word in {"{curly braces}"} to make it a blank, like
            “Bake at {"{temp}"} until {"{doneness}"}”.
          </p>
          <ul className="list-plain">
            {mine.map((t) => (
              <li key={t.id}>
                <span>{t.text}</span>
                <button className="btn small quiet danger" onClick={() => api.deleteTemplate(t.id!).then(load)}>Remove</button>
              </li>
            ))}
          </ul>
          <div className="row" style={{ marginTop: 10 }}>
            <input className="input" style={{ flex: "3 1 200px" }} value={newTpl} onChange={(e) => setNewTpl(e.target.value)} placeholder="Sprinkle with colored sugar." onKeyDown={(e) => e.key === "Enter" && add()} />
            <button className="btn" onClick={add}>Add phrase</button>
          </div>
        </div>

        <div className="card">
          <h2 style={{ fontSize: 22, marginBottom: 6 }}>Your recipes, your data</h2>
          <p className="hint" style={{ marginTop: 0 }}>
            Download every recipe in the standard recipe format that most recipe apps can import. A good backup, too.
          </p>
          <a className="btn" href="/api/export">Download all recipes</a>
        </div>

        <p style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <span className="hint" style={{ flex: 1 }}>Signed in as {me.user.display_name} ({me.user.email})</span>
          <button className="btn" onClick={() => api.logout().then(refresh)}>Log out</button>
        </p>
      </main>
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
