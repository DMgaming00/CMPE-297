"""D) Production code review assistant.

root (LlmAgent router)
├── review_pipeline (Sequential)
│   ├── intake                 LLM  - registers pasted code / workspace files (tools)
│   ├── static_analysis        DET  - AST security/correctness/maintainability/style/tests
│   ├── specialist_panel       PAR  - correctness | security | testing | maintainability
│   │                                 (LLM, structured SpecialistReview output)
│   ├── findings_synthesis     DET  - validate, de-duplicate, rank, verdict
│   └── report_writer          LLM  - final markdown review (cannot alter findings)
└── fix_pipeline (Sequential)
    ├── fix_loop (Loop, max 3) - fixer (LLM) -> fix_validator (DET, exits when no P0/P1)
    └── fix_reporter           LLM
DET = deterministic Python agent, no model call.  Reviewed code is never executed.
"""

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent

from adk_shared.config import advanced_model, fast_model

from . import prompts
from .models import SpecialistReview
from .stages import (
    FindingsSynthesisAgent,
    FixValidationAgent,
    StaticAnalysisAgent,
    skip_if_no_code,
    skip_specialist_if_no_code,
    start_new_review,
)
from .tools import (
    list_workspace_files,
    load_workspace_files,
    submit_code_for_review,
    submit_fixed_code,
)


def _specialist(name: str, instruction: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=advanced_model(),
        instruction=instruction,
        include_contents="none",
        output_schema=SpecialistReview,
        output_key=name.replace("_reviewer", "_review"),
        before_agent_callback=skip_specialist_if_no_code,
    )


intake = LlmAgent(
    name="intake",
    model=fast_model(),
    instruction=prompts.INTAKE,
    tools=[submit_code_for_review, load_workspace_files],
    before_agent_callback=start_new_review,
)

specialist_panel = ParallelAgent(
    name="specialist_panel",
    sub_agents=[
        _specialist("correctness_reviewer", prompts.CORRECTNESS),
        _specialist("security_reviewer", prompts.SECURITY),
        _specialist("testing_reviewer", prompts.TESTING),
        _specialist("maintainability_reviewer", prompts.MAINTAINABILITY),
    ],
)

report_writer = LlmAgent(
    name="report_writer",
    model=advanced_model(),
    instruction=prompts.REPORT_WRITER,
    include_contents="none",
    before_agent_callback=skip_if_no_code,
)

review_pipeline = SequentialAgent(
    name="review_pipeline",
    description="Reviews submitted Python code and produces prioritised P0-P3 findings.",
    sub_agents=[intake, StaticAnalysisAgent(name="static_analysis"), specialist_panel,
                FindingsSynthesisAgent(name="findings_synthesis"), report_writer],
)

fix_pipeline = SequentialAgent(
    name="fix_pipeline",
    description="Fixes blocking findings from the last review and re-validates them.",
    sub_agents=[
        LoopAgent(name="fix_loop", max_iterations=3, sub_agents=[
            LlmAgent(name="fixer", model=advanced_model(), instruction=prompts.FIXER,
                     include_contents="none", tools=[submit_fixed_code],
                     before_agent_callback=skip_if_no_code),
            FixValidationAgent(name="fix_validator"),
        ]),
        LlmAgent(name="fix_reporter", model=fast_model(), instruction=prompts.FIX_REPORTER,
                 include_contents="none"),
    ],
)

root_agent = LlmAgent(
    name="code_review_assistant",
    model=fast_model(),
    description="Multi-stage Python code reviewer with static analysis, specialist "
                "reviewers, P0-P3 findings and an automated fix/re-validate loop.",
    instruction=prompts.ROUTER,
    tools=[list_workspace_files],
    sub_agents=[review_pipeline, fix_pipeline],
)
