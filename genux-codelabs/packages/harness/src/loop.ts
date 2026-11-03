/* eslint-disable @typescript-eslint/no-explicit-any -- heterogeneous tool registry: each tool has its own argument type */
import { z } from "zod";
import type { ChatMessage, ChatModel, HarnessConfig, HarnessEvent, Tool, ToolSpec } from "./types";

export const toToolSpecs = (tools: Tool<any>[]): ToolSpec[] =>
  tools.map((t) => ({ name: t.name, description: t.description, parameters: z.toJSONSchema(t.schema) as Record<string, unknown> }));

export interface RunOptions {
  model: ChatModel;
  tools: Tool<any>[];
  config: HarnessConfig;
  messages: ChatMessage[];
  onEvent?: (e: HarnessEvent) => void;
}
export interface RunResult {
  messages: ChatMessage[];
  steps: number;
  ok: boolean;
}

/**
 * The agent loop: prompt → model → tool calls → (validated) results → model → ... → final text.
 * Failure policy: a bad tool call, an unauthorized tool or a rejected UI spec becomes an `Error:` tool message
 * and the loop continues, so the model can correct itself. Only a model failure or the step cap ends the run.
 */
export async function runHarness({ model, tools, config, messages: initial, onEvent = () => {} }: RunOptions): Promise<RunResult> {
  const messages = [...initial];
  if (config.system && messages[0]?.role !== "system") messages.unshift({ role: "system", content: config.system });
  const visible = tools.filter((t) => config.allowedTools.includes(t.name));
  const specs = toToolSpecs(visible);
  onEvent({ type: "run_started", model: model.name, tools: visible.map((t) => t.name) });

  let steps = 0;
  try {
    while (steps < config.maxSteps) {
      steps++;
      const res = await model.complete(messages, specs);
      if (res.text) onEvent({ type: "text", text: res.text });
      messages.push({ role: "assistant", content: res.text ?? "", toolCalls: res.toolCalls.length ? res.toolCalls : undefined });
      if (res.toolCalls.length === 0) {
        onEvent({ type: "run_finished", steps });
        return { messages, steps, ok: true };
      }
      for (const call of res.toolCalls) {
        onEvent({ type: "tool_call", id: call.id, name: call.name, args: call.args });
        const fail = (error: string) => {
          onEvent({ type: "tool_error", id: call.id, name: call.name, error });
          messages.push({ role: "tool", name: call.name, toolCallId: call.id, content: `Error: ${error}` });
        };
        const tool = tools.find((t) => t.name === call.name);
        if (!tool || !config.allowedTools.includes(call.name)) {
          fail(`tool "${call.name}" is not permitted`);
          continue;
        }
        const parsed = tool.schema.safeParse(call.args);
        if (!parsed.success) {
          fail(`invalid arguments: ${parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ")}`);
          continue;
        }
        try {
          const out = await tool.run(parsed.data);
          onEvent({ type: "tool_result", id: call.id, name: call.name, content: out.content.slice(0, 4000), data: out.data });
          if (out.ui) onEvent({ type: "ui", id: call.id, payload: out.ui });
          messages.push({ role: "tool", name: call.name, toolCallId: call.id, content: out.content });
        } catch (e) {
          fail(e instanceof Error ? e.message : String(e));
        }
      }
    }
    onEvent({ type: "run_error", message: `stopped after ${config.maxSteps} steps (step limit)` });
    return { messages, steps, ok: false };
  } catch (e) {
    onEvent({ type: "run_error", message: e instanceof Error ? e.message : String(e) });
    return { messages, steps, ok: false };
  }
}
