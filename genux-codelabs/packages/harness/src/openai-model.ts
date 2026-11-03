import type { ChatMessage, ChatModel, ModelResponse, ToolSpec } from "./types";

export interface LlmConfig {
  provider: "mock" | "openai-compatible";
  baseUrl: string;
  apiKey: string;
  model: string;
  maxSteps: number;
}

/** Reads env only; the key is never logged or serialized into events. */
export function loadLlmConfig(env: Record<string, string | undefined> = process.env): LlmConfig {
  return {
    provider: env.LLM_PROVIDER === "openai-compatible" ? "openai-compatible" : "mock",
    baseUrl: (env.LLM_BASE_URL ?? "https://api.openai.com/v1").replace(/\/$/, ""),
    apiKey: env.LLM_API_KEY ?? "",
    model: env.LLM_MODEL ?? "gpt-4o-mini",
    maxSteps: Math.max(1, Math.min(Number(env.HARNESS_MAX_STEPS) || 6, 20)),
  };
}

/** Optional real provider (any OpenAI-compatible chat-completions endpoint). Isolated behind env vars. */
export class OpenAICompatibleModel implements ChatModel {
  readonly name: string;
  constructor(private readonly cfg: LlmConfig) {
    if (!cfg.apiKey) throw new Error("LLM_API_KEY is required when LLM_PROVIDER=openai-compatible");
    this.name = cfg.model;
  }

  async complete(messages: ChatMessage[], tools: ToolSpec[]): Promise<ModelResponse> {
    const body = {
      model: this.cfg.model,
      messages: messages.map((m) => {
        if (m.role === "tool") return { role: "tool", tool_call_id: m.toolCallId, content: m.content };
        if (m.role === "assistant" && m.toolCalls) {
          return { role: "assistant", content: m.content || null, tool_calls: m.toolCalls.map((c) => ({ id: c.id, type: "function", function: { name: c.name, arguments: JSON.stringify(c.args) } })) };
        }
        return { role: m.role, content: m.content };
      }),
      tools: tools.map((t) => ({ type: "function", function: { name: t.name, description: t.description, parameters: t.parameters } })),
    };
    const res = await fetch(`${this.cfg.baseUrl}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.cfg.apiKey}` },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`model endpoint answered ${res.status}`); // never echo headers/body: they may contain secrets
    const json = (await res.json()) as { choices?: { message?: { content?: string | null; tool_calls?: { id: string; function: { name: string; arguments: string } }[] } }[] };
    const msg = json.choices?.[0]?.message;
    if (!msg) throw new Error("model returned no message");
    return {
      text: msg.content ?? undefined,
      toolCalls: (msg.tool_calls ?? []).map((c) => {
        let args: unknown = {};
        try {
          args = JSON.parse(c.function.arguments);
        } catch {
          args = { __malformed: c.function.arguments.slice(0, 200) }; // fails schema validation → correction loop
        }
        return { id: c.id, name: c.function.name, args };
      }),
    };
  }
}
