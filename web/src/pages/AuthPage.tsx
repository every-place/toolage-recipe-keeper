import { useState, type FormEvent } from "react";
import { api } from "../api";

export default function AuthPage({ onDone }: { onDone: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [joining, setJoining] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", display_name: "", household_name: "", join_code: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "login") await api.login(form.email, form.password);
      else
        await api.signup({
          email: form.email,
          password: form.password,
          display_name: form.display_name,
          household_name: joining ? undefined : form.household_name || undefined,
          join_code: joining ? form.join_code : undefined,
        });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <div className="logo">
        <h1>Recipe Keeper</h1>
        <p>the family recipe box, kept safe</p>
      </div>
      <div className="tabs">
        <button className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>Log in</button>
        <button className={mode === "signup" ? "on" : ""} onClick={() => setMode("signup")}>Create account</button>
      </div>
      <form onSubmit={submit} className="card">
        {error && <div className="error">{error}</div>}
        {mode === "signup" && (
          <label className="field">
            <span>Your name</span>
            <input className="input" value={form.display_name} onChange={set("display_name")} autoComplete="given-name" required />
          </label>
        )}
        <label className="field">
          <span>Email</span>
          <input className="input" type="email" value={form.email} onChange={set("email")} autoComplete="email" required />
        </label>
        <label className="field">
          <span>Password{mode === "signup" && " (at least 8 characters)"}</span>
          <input
            className="input"
            type="password"
            value={form.password}
            onChange={set("password")}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={mode === "signup" ? 8 : undefined}
            required
          />
        </label>
        {mode === "signup" && (
          <>
            <div className="tabs">
              <button type="button" className={!joining ? "on" : ""} onClick={() => setJoining(false)}>Start a recipe box</button>
              <button type="button" className={joining ? "on" : ""} onClick={() => setJoining(true)}>Join my family's</button>
            </div>
            {joining ? (
              <label className="field">
                <span>Family code</span>
                <input className="input" value={form.join_code} onChange={set("join_code")} placeholder="ABCD-1234" autoCapitalize="characters" required />
                <p className="hint">Find it in Settings on a family member's Recipe Keeper.</p>
              </label>
            ) : (
              <label className="field">
                <span>Name your recipe box</span>
                <input className="input" value={form.household_name} onChange={set("household_name")} placeholder="The Smith family kitchen" />
              </label>
            )}
          </>
        )}
        <button className="btn primary" style={{ width: "100%" }} disabled={busy}>
          {mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
    </div>
  );
}
