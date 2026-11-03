import { EventType } from "@ag-ui/core";
import type { BaseEvent } from "@ag-ui/core";
import type { HarnessEvent } from "./types";

export interface BridgeState {
  threadId: string;
  runId: string;
  seq: number;
  state: Record<string, unknown>;
}
export const newBridge = (threadId: string, runId: string): BridgeState => ({ threadId, runId, seq: 0, state: {} });

/** Map one harness event to AG-UI events. A loop's callbacks become a browser's typed event stream. */
export function toAgUi(e: HarnessEvent, b: BridgeState): BaseEvent[] {
  const id = (p: string) => `${p}_${b.runId}_${++b.seq}`;
  switch (e.type) {
    case "run_started":
      return [{ type: EventType.RUN_STARTED, threadId: b.threadId, runId: b.runId } as BaseEvent];
    case "text": {
      const messageId = id("msg");
      return [
        { type: EventType.TEXT_MESSAGE_START, messageId, role: "assistant" },
        ...(e.text.match(/.{1,24}/gs) ?? []).map((delta) => ({ type: EventType.TEXT_MESSAGE_CONTENT, messageId, delta })),
        { type: EventType.TEXT_MESSAGE_END, messageId },
      ] as BaseEvent[];
    }
    case "tool_call": {
      const args = JSON.stringify(e.args ?? {});
      return [
        { type: EventType.TOOL_CALL_START, toolCallId: e.id, toolCallName: e.name },
        ...(args.match(/.{1,48}/gs) ?? []).map((delta) => ({ type: EventType.TOOL_CALL_ARGS, toolCallId: e.id, delta })),
        { type: EventType.TOOL_CALL_END, toolCallId: e.id },
      ] as BaseEvent[];
    }
    case "tool_result":
      return [{ type: EventType.TOOL_CALL_RESULT, messageId: id("res"), toolCallId: e.id, content: e.content.slice(0, 2000), role: "tool" } as BaseEvent];
    case "tool_error":
      return [{ type: EventType.TOOL_CALL_RESULT, messageId: id("res"), toolCallId: e.id, content: `Error: ${e.error}`, role: "tool" } as BaseEvent];
    case "ui": {
      b.state = { ...b.state, ui: e.payload };
      return [{ type: EventType.STATE_SNAPSHOT, snapshot: b.state } as BaseEvent];
    }
    case "run_finished":
      return [{ type: EventType.RUN_FINISHED, threadId: b.threadId, runId: b.runId } as BaseEvent];
    case "run_error":
      return [{ type: EventType.RUN_ERROR, message: e.message } as BaseEvent];
  }
}
