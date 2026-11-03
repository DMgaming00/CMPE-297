export type Intent = "compare" | "dashboard" | "widget" | "broken" | "forbidden" | "action" | "chat";

export function classifyIntent(prompt: string): Intent {
  const p = prompt.toLowerCase();
  if (p.startsWith("[ui-action]")) return "action";
  if (/delete|drop table|rm -rf|exfiltrate/.test(p)) return "forbidden";
  if (/invalid|broken|break it|malformed/.test(p)) return "broken";
  if (/calculator|budget|saving|interactive|widget|simulate/.test(p)) return "widget";
  if (/compar|versus|\bvs\b|side by side/.test(p)) return "compare";
  if (/dashboard|overview|shortlist|show me|list|find|search|best/.test(p)) return "dashboard";
  return "chat";
}

export function parseBudget(prompt: string): number | undefined {
  const m = prompt.match(/\$\s?(\d[\d,]*)|under\s+(\d[\d,]*)/i);
  const raw = m?.[1] ?? m?.[2];
  return raw ? Number(raw.replace(/,/g, "")) : undefined;
}
