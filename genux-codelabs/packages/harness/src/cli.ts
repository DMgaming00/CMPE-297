import { renderSpecText } from "./text-render";
import { createModel } from "./factory";
import { runHarness } from "./loop";
import { defaultTools } from "./tools";
import type { UiTarget } from "./scripted-model";

const args = process.argv.slice(2);
const uiFlag = args.indexOf("--ui");
const target = (uiFlag >= 0 ? args.splice(uiFlag, 2)[1] : "json-render") as UiTarget;
const prompt = args.join(" ") || "compare laptops under $1500";

const { model, config } = createModel(target);
console.log(`── harness · model=${model.name} · maxSteps=${config.maxSteps}\n> ${prompt}\n`);
const result = await runHarness({
  model, tools: defaultTools, config, messages: [{ role: "user", content: prompt }],
  onEvent: (e) => {
    switch (e.type) {
      case "tool_call": console.log(`→ tool ${e.name} ${JSON.stringify(e.args).slice(0, 100)}`); break;
      case "tool_result": console.log(`✓ ${e.name}: ${e.content.slice(0, 80)}`); break;
      case "tool_error": console.log(`✗ ${e.name}: ${e.error.split("\n")[0]}`); break;
      case "ui":
        console.log(e.payload.kind === "json-render" ? `\n${renderSpecText(e.payload.spec)}\n` : e.payload.kind === "openui" ? `\n${e.payload.program}\n` : `\n[sandboxed html widget: ${e.payload.title}]\n`);
        break;
      case "text": console.log(`agent: ${e.text}`); break;
      case "run_error": console.log(`run error: ${e.message}`); break;
      default: break;
    }
  },
});
process.exit(result.ok ? 0 : 1);
