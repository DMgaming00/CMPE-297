import type { z } from "zod";
import type { Spec } from "@genux/schemas";

export interface ToolCall {
  id: string;
  name: string;
  args: unknown;
}
export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
  toolCallId?: string;
  name?: string;
}
export interface ModelResponse {
  text?: string;
  toolCalls: ToolCall[];
}
export interface ToolSpec {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}
export interface ChatModel {
  readonly name: string;
  complete(messages: ChatMessage[], tools: ToolSpec[]): Promise<ModelResponse>;
}

/** What a render tool hands to the UI surface. The model only ever sees the short `content` string. */
export type UiPayload =
  | { kind: "json-render"; spec: Spec }
  | { kind: "openui"; program: string }
  | { kind: "html"; title: string; document: string };

export interface ToolOutcome {
  content: string;
  data?: unknown;
  ui?: UiPayload;
}
export interface Tool<A = unknown> {
  name: string;
  description: string;
  schema: z.ZodType<A>;
  run(args: A): Promise<ToolOutcome> | ToolOutcome;
}

export type HarnessEvent =
  | { type: "run_started"; model: string; tools: string[] }
  | { type: "text"; text: string }
  | { type: "tool_call"; id: string; name: string; args: unknown }
  | { type: "tool_result"; id: string; name: string; content: string; data?: unknown }
  | { type: "tool_error"; id: string; name: string; error: string }
  | { type: "ui"; id: string; payload: UiPayload }
  | { type: "run_finished"; steps: number }
  | { type: "run_error"; message: string };

export interface HarnessConfig {
  maxSteps: number;
  /** Authorization boundary: the model may only call tools named here. */
  allowedTools: string[];
  system?: string;
}
