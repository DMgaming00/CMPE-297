import { EventType } from "@ag-ui/core";
import type { BaseEvent } from "@ag-ui/core";
import { createModel, defaultTools, newBridge, runHarness, toAgUi } from "@genux/harness";
import { ITEMS, budgetWidgetHtml, comparisonSpec, compareItems, sleep } from "@genux/shared";
import { validateSpec } from "@genux/schemas";

export type Demo = "static" | "declarative" | "open-ended" | "approval" | "harness";
export interface RunCtx {
  threadId: string;
  runId: string;
  demo: Demo;
  prompt: string;
  /** Tool results the client sent back (frontend tools). */
  toolResults: Record<string, string>;
  env: Record<string, string | undefined>;
}
const mid = (c: RunCtx, n: string) => `msg_${c.runId}_${n}`;

async function* say(c: RunCtx, key: string, text: string): AsyncGenerator<BaseEvent> {
  const messageId = mid(c, key);
  yield { type: EventType.TEXT_MESSAGE_START, messageId, role: "assistant" } as BaseEvent;
  for (const delta of text.match(/.{1,12}/gs) ?? []) {
    yield { type: EventType.TEXT_MESSAGE_CONTENT, messageId, delta } as BaseEvent;
    await sleep(40);
  }
  yield { type: EventType.TEXT_MESSAGE_END, messageId } as BaseEvent;
}

async function* toolCall(c: RunCtx, id: string, name: string, args: unknown): AsyncGenerator<BaseEvent> {
  yield { type: EventType.TOOL_CALL_START, toolCallId: id, toolCallName: name, parentMessageId: mid(c, "tools") } as BaseEvent;
  for (const delta of JSON.stringify(args).match(/.{1,20}/gs) ?? []) {
    yield { type: EventType.TOOL_CALL_ARGS, toolCallId: id, delta } as BaseEvent;
    await sleep(30);
  }
  yield { type: EventType.TOOL_CALL_END, toolCallId: id } as BaseEvent;
}

/** The agent is an async generator of typed AG-UI events. The transport (SSE) is a separate concern. */
export async function* runAgent(c: RunCtx): AsyncGenerator<BaseEvent> {
  yield { type: EventType.RUN_STARTED, threadId: c.threadId, runId: c.runId } as BaseEvent;
  try {
    yield* body(c);
    yield { type: EventType.RUN_FINISHED, threadId: c.threadId, runId: c.runId } as BaseEvent;
  } catch (e) {
    yield { type: EventType.RUN_ERROR, message: e instanceof Error ? e.message : "agent failed" } as BaseEvent;
  }
}

async function* body(c: RunCtx): AsyncGenerator<BaseEvent> {
  switch (c.demo) {
    case "static": {
      // Tool-based generative UI: the agent calls a tool whose NAME the frontend maps to a pre-built component.
      yield { type: EventType.STEP_STARTED, stepName: "pick_item" } as BaseEvent;
      yield* say(c, "a", "Looking for the best-rated ultraportable… ");
      yield* toolCall(c, `tc_${c.runId}_1`, "show_item_card", { id: "air-13" });
      yield { type: EventType.TOOL_CALL_RESULT, messageId: mid(c, "r1"), toolCallId: `tc_${c.runId}_1`, content: "rendered", role: "tool" } as BaseEvent;
      yield { type: EventType.STEP_FINISHED, stepName: "pick_item" } as BaseEvent;
      yield* say(c, "b", "The Aurora Air 13 is drawn by a component written in advance.");
      return;
    }
    case "declarative": {
      // Generative UI as shared state: the UI spec lives in `state.ui`; later changes are JSON Patch deltas.
      const spec = validateSpec(comparisonSpec(compareItems(["air-13", "vertex-13", "nimbus-14"])));
      if (!spec.ok) throw new Error("agent produced an invalid spec");
      yield { type: EventType.STATE_SNAPSHOT, snapshot: { status: "planning", progress: 0, ui: null } } as BaseEvent;
      yield* say(c, "a", "Comparing three laptops and describing the UI as data… ");
      for (const p of [30, 60]) {
        await sleep(250);
        yield { type: EventType.STATE_DELTA, delta: [{ op: "replace", path: "/progress", value: p }] } as BaseEvent;
      }
      yield { type: EventType.STATE_DELTA, delta: [{ op: "replace", path: "/ui", value: spec.spec }, { op: "replace", path: "/progress", value: 100 }, { op: "replace", path: "/status", value: "done" }] } as BaseEvent;
      yield* say(c, "b", "The spec arrived as a state patch and was validated before rendering.");
      return;
    }
    case "open-ended": {
      // CUSTOM events carry anything the protocol has no type for. Here: sandboxed HTML (the host must contain it).
      yield* say(c, "a", "Writing a small interactive calculator… ");
      yield { type: EventType.CUSTOM, name: "html_artifact", value: { title: "Budget calculator", document: budgetWidgetHtml(ITEMS.slice(0, 4)) } } as BaseEvent;
      yield* say(c, "b", "It runs in a sandboxed iframe with no network access.");
      return;
    }
    case "approval": {
      // Frontend tool / human-in-the-loop: the run ends with an unanswered tool call; the client answers and re-runs.
      const id = `tc_confirm`;
      const answer = c.toolResults[id];
      if (answer === undefined) {
        yield* say(c, "a", "I can shortlist the 3 best-rated laptops. I need your approval first. ");
        yield* toolCall(c, id, "confirm_plan", { plan: "Search catalog, rank by rating, show top 3", costUsd: 0 });
        return;
      }
      if (answer !== "approved") {
        yield* say(c, "b", "Understood, I will not run the plan.");
        return;
      }
      const top = [...ITEMS].sort((a, b) => b.rating - a.rating).slice(0, 3);
      yield { type: EventType.STATE_SNAPSHOT, snapshot: { status: "done", shortlist: top.map((i) => `${i.name} (${i.rating})`) } } as BaseEvent;
      yield* say(c, "b", "Approved. The shortlist is in shared state.");
      return;
    }
    case "harness": {
      // AG-UI from the harness: every harness callback becomes an AG-UI event.
      const { model, config } = createModel("json-render", c.env);
      const queue: BaseEvent[] = [];
      const bridge = newBridge(c.threadId, c.runId);
      const p = runHarness({ model, tools: defaultTools, config, messages: [{ role: "user", content: c.prompt || "compare laptops under $1500" }], onEvent: (e) => {
        if (e.type === "run_started" || e.type === "run_finished") return; // the outer generator owns the lifecycle
        queue.push(...toAgUi(e, bridge));
      } });
      let done = false;
      void p.finally(() => (done = true));
      while (!done || queue.length) {
        const ev = queue.shift();
        if (ev) { yield ev; await sleep(60); } else await sleep(20);
      }
      return;
    }
  }
}
