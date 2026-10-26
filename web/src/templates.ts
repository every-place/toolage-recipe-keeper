import type { Template } from "./api";

export const BLANK = "___";

// "Bake at {temp} for {time}" -> "Bake at ___ for ___" and ["temp", "time"]
export function expandTemplate(text: string): { text: string; slots: string[] } {
  const slots: string[] = [];
  const out = text.replace(/\{(\w+)\}/g, (_, name: string) => {
    slots.push(name);
    return BLANK;
  });
  return { text: out, slots };
}

const words = (s: string) =>
  s
    .toLowerCase()
    .replace(/\{\w+\}/g, " ")
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);

// Suggest templates for what's been typed so far. A template matches when
// its words start with what was typed ("pre" -> "Preheat oven..."), or when
// every typed word starts some word in the template ("bake until").
export function suggest(typed: string, templates: Template[], limit = 4): Template[] {
  const t = typed.trim().toLowerCase();
  if (t.length < 2) return [];
  const typedWords = words(t);
  if (!typedWords.length) return [];
  const scored: [number, Template][] = [];
  for (const tpl of templates) {
    const plain = tpl.text.toLowerCase().replace(/\{\w+\}/g, BLANK);
    if (plain === t) continue;
    const tw = words(tpl.text);
    let score = 0;
    if (plain.startsWith(t)) score = 3;
    else if (tw.length && typedWords.every((w) => tw.some((x) => x.startsWith(w)))) score = 1;
    if (tpl.custom && score) score += 0.5; // the family's own phrasing first
    if (score) scored.push([score, tpl]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.slice(0, limit).map(([, tpl]) => tpl);
}

// Fill the first blank with a value.
export function fillFirstBlank(text: string, value: string): string {
  const i = text.indexOf(BLANK);
  if (i < 0) return text;
  return text.slice(0, i) + value + text.slice(i + BLANK.length);
}
