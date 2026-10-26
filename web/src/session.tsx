import { createContext, useContext } from "react";
import type { Me } from "./api";

export const SessionContext = createContext<{ me: Me; refresh: () => Promise<void> } | null>(null);

export function useSession() {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession outside SessionContext");
  return s;
}
