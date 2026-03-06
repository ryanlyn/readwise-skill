from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trace_collector import Scenario, collect_trace

QUALITATIVE_FINDINGS = [
    "The skill traces are more procedural and easier to audit. For book tasks the model typically resolves a book first, then fetches highlights by `book_id`.",
    "The MCP traces are more one-shot. The model usually issues a broad search and then summarizes a large raw JSON payload, which reads smoothly but is less transparent to inspect.",
    "The clearest behavioral gap is constraint fidelity. In `compound_filter_query`, the skill path enforces both tag and recency. The MCP path cannot verify the recency constraint from the returned payload, so it falls back to a caveated partial answer.",
    "The skill path is better at entity disambiguation. In book-oriented scenarios it resolves concrete ids first; the MCP path relies on title search over the whole corpus.",
    "The MCP payload gives the model richer provenance, but also far more irrelevant structure. The skill payload is leaner and keeps the model focused, at the cost of less context.",
    "Across runs, the qualitative pattern was stable: skill answers were narrower and more literal; MCP answers were broader and more synthetic.",
]


@dataclass(slots=True)
class BenchmarkConfig:
    repeats_per_scenario: int
    scenarios: list[Scenario]


@dataclass(slots=True)
class ScenarioSummary:
    scenario_id: str
    skill_runs: int
    mcp_runs: int
    skill_success: int
    mcp_success: int
    skill_total_tokens_median: float
    mcp_total_tokens_median: float
    skill_tool_output_tokens_median: float
    mcp_tool_output_tokens_median: float
    skill_turns_median: float
    mcp_turns_median: float


def _parse_quoted(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
        return value[1:-1]
    return value


def load_prompts(path: Path) -> BenchmarkConfig:
    repeats = 1
    scenarios: list[Scenario] = []
    current_id: str | None = None
    current_prompt: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("repeats_per_scenario:"):
            repeats = int(line.split(":", 1)[1].strip())
            continue
        if line.startswith("- id:"):
            if current_id and current_prompt:
                scenarios.append(Scenario(scenario_id=current_id, prompt=current_prompt))
            current_id = _parse_quoted(line.split(":", 1)[1].strip())
            current_prompt = None
            continue
        if line.startswith("prompt:") and current_id:
            current_prompt = _parse_quoted(line.split(":", 1)[1].strip())
    if current_id and current_prompt:
        scenarios.append(Scenario(scenario_id=current_id, prompt=current_prompt))
    if not scenarios:
        raise RuntimeError(f"No scenarios parsed from {path}")
    return BenchmarkConfig(repeats_per_scenario=repeats, scenarios=scenarios)


def _ensure_env() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required.")
    if not (os.getenv("READWISE_API_TOKEN") or os.getenv("READWISE_TOKEN")):
        raise RuntimeError("READWISE_API_TOKEN or READWISE_TOKEN is required.")


def _select_scenarios(all_scenarios: list[Scenario], selected: set[str] | None) -> list[Scenario]:
    if not selected:
        return all_scenarios
    scenarios = [scenario for scenario in all_scenarios if scenario.scenario_id in selected]
    if not scenarios:
        raise RuntimeError(f"No matching scenarios for selection: {sorted(selected)}")
    return scenarios


def _approaches(value: str) -> list[str]:
    return ["skill", "mcp"] if value == "both" else [value]


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _safe_ratio(a: float, b: float) -> float:
    return 0.0 if b == 0 else a / b


def _metric_values(runs: list[dict], key: str) -> list[float]:
    return [float((run.get("metrics") or {}).get(key, 0) or 0) for run in runs]


def _collect_summaries(results: list[dict]) -> list[ScenarioSummary]:
    grouped: dict[str, dict[str, list[dict]]] = {}
    for result in results:
        scenario_id = str(result["scenario_id"])
        approach = str(result["approach"])
        grouped.setdefault(scenario_id, {}).setdefault(approach, []).append(result)

    summaries: list[ScenarioSummary] = []
    for scenario_id in sorted(grouped):
        skill_runs = grouped[scenario_id].get("skill", [])
        mcp_runs = grouped[scenario_id].get("mcp", [])
        summaries.append(
            ScenarioSummary(
                scenario_id=scenario_id,
                skill_runs=len(skill_runs),
                mcp_runs=len(mcp_runs),
                skill_success=sum(1 for run in skill_runs if run.get("status") == "success"),
                mcp_success=sum(1 for run in mcp_runs if run.get("status") == "success"),
                skill_total_tokens_median=_median(_metric_values(skill_runs, "total_tokens")),
                mcp_total_tokens_median=_median(_metric_values(mcp_runs, "total_tokens")),
                skill_tool_output_tokens_median=_median(_metric_values(skill_runs, "tool_output_tokens")),
                mcp_tool_output_tokens_median=_median(_metric_values(mcp_runs, "tool_output_tokens")),
                skill_turns_median=_median(_metric_values(skill_runs, "total_turns")),
                mcp_turns_median=_median(_metric_values(mcp_runs, "total_turns")),
            )
        )
    return summaries


def _bar(other_tokens: float, tool_tokens: float, width: int, scale: float) -> str:
    other_width = max(1, round(other_tokens / scale)) if other_tokens else 0
    tool_width = max(1, round(tool_tokens / scale)) if tool_tokens else 0
    if other_width + tool_width > width:
        overflow = other_width + tool_width - width
        if tool_width > overflow:
            tool_width -= overflow
        else:
            other_width = max(1, other_width - (overflow - tool_width + 1))
            tool_width = 1
    return f"[{'=' * other_width}{'#' * tool_width}]"


def _render_report(
    *,
    results: list[dict],
    summaries: list[ScenarioSummary],
    model: str,
    prompts_path: Path,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    token_modes = sorted({str(item.get("token_counter_mode", "")) for item in results if item.get("token_counter_mode")})

    overall_skill_total = _median([summary.skill_total_tokens_median for summary in summaries])
    overall_mcp_total = _median([summary.mcp_total_tokens_median for summary in summaries])
    overall_skill_tool = _median([summary.skill_tool_output_tokens_median for summary in summaries])
    overall_mcp_tool = _median([summary.mcp_tool_output_tokens_median for summary in summaries])
    overall_skill_turns = _median([summary.skill_turns_median for summary in summaries])
    overall_mcp_turns = _median([summary.mcp_turns_median for summary in summaries])
    overall_skill_other = max(0.0, overall_skill_total - overall_skill_tool)
    overall_mcp_other = max(0.0, overall_mcp_total - overall_mcp_tool)

    scale = max((overall_skill_total, overall_mcp_total, 1.0)) / 32

    lines: list[str] = []
    lines.append("# Token Efficiency Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append(f"Prompts: `{prompts_path.name}`")
    lines.append(f"Model: `{model}`")
    lines.append(f"Tool token counter mode: `{', '.join(token_modes)}`")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append(f"- `total_tokens` ratio (skill/mcp): `{_safe_ratio(overall_skill_total, overall_mcp_total):.3f}`")
    lines.append(f"- `tool_output_tokens` ratio (skill/mcp): `{_safe_ratio(overall_skill_tool, overall_mcp_tool):.3f}`")
    lines.append(f"- `total_turns` ratio (skill/mcp): `{_safe_ratio(overall_skill_turns, overall_mcp_turns):.3f}`")
    lines.append("")

    lines.append("`total_tokens` is the end-to-end measure for this harness: user prompt, system prompt, tool schema, tool-call arguments, tool results, and model output.")
    lines.append("`tool_output_tokens` is diagnostic only: just the text returned from tools to the model. It does not include tool descriptions, system prompts, or full SKILL.md / MCP docs.")
    lines.append("Those non-tool costs only appear inside `total_tokens` to the extent this harness actually injects them. This implementation uses minimal system prompts plus JSON tool schemas, not full SKILL.md.")
    lines.append("")

    lines.append("## Token Shape")
    lines.append("")
    lines.append("Approximate median-of-medians breakdown:")
    lines.append("")
    lines.append(f"`skill` { _bar(overall_skill_other, overall_skill_tool, 32, scale) } other~{overall_skill_other:.0f} + tool~{overall_skill_tool:.0f} = total~{overall_skill_total:.0f}")
    lines.append(f"`mcp`   { _bar(overall_mcp_other, overall_mcp_tool, 32, scale) } other~{overall_mcp_other:.0f} + tool~{overall_mcp_tool:.0f} = total~{overall_mcp_total:.0f}")
    lines.append("")
    lines.append("Legend: `=` non-tool tokens, `#` tool-result payload tokens")
    lines.append("")

    lines.append("## Scenario Results")
    lines.append("")
    lines.append(
        "| Scenario | Skill success | MCP success | Skill total tok (med) | MCP total tok (med) | Total ratio | Skill tool out (med) | MCP tool out (med) | Out ratio | Skill turns (med) | MCP turns (med) | Turn ratio |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.scenario_id} | "
            f"{summary.skill_success}/{summary.skill_runs} | "
            f"{summary.mcp_success}/{summary.mcp_runs} | "
            f"{summary.skill_total_tokens_median:.1f} | "
            f"{summary.mcp_total_tokens_median:.1f} | "
            f"{_safe_ratio(summary.skill_total_tokens_median, summary.mcp_total_tokens_median):.3f} | "
            f"{summary.skill_tool_output_tokens_median:.1f} | "
            f"{summary.mcp_tool_output_tokens_median:.1f} | "
            f"{_safe_ratio(summary.skill_tool_output_tokens_median, summary.mcp_tool_output_tokens_median):.3f} | "
            f"{summary.skill_turns_median:.1f} | "
            f"{summary.mcp_turns_median:.1f} | "
            f"{_safe_ratio(summary.skill_turns_median, summary.mcp_turns_median):.3f} |"
        )
    lines.append("")

    lines.append("## Scenario Token Shape")
    lines.append("")
    lines.append("Each bar splits median total tokens into non-tool tokens (`=`) and tool-result payload tokens (`#`).")
    lines.append("")
    for summary in summaries:
        skill_other = max(0.0, summary.skill_total_tokens_median - summary.skill_tool_output_tokens_median)
        mcp_other = max(0.0, summary.mcp_total_tokens_median - summary.mcp_tool_output_tokens_median)
        scenario_scale = max(summary.skill_total_tokens_median, summary.mcp_total_tokens_median, 1.0) / 28
        lines.append(f"`{summary.scenario_id}`")
        lines.append(
            f"`skill` { _bar(skill_other, summary.skill_tool_output_tokens_median, 28, scenario_scale) } "
            f"other~{skill_other:.0f} + tool~{summary.skill_tool_output_tokens_median:.0f} = total~{summary.skill_total_tokens_median:.0f}"
        )
        lines.append(
            f"`mcp`   { _bar(mcp_other, summary.mcp_tool_output_tokens_median, 28, scenario_scale) } "
            f"other~{mcp_other:.0f} + tool~{summary.mcp_tool_output_tokens_median:.0f} = total~{summary.mcp_total_tokens_median:.0f}"
        )
        lines.append("")

    lines.append("## Qualitative Findings")
    lines.append("")
    lines.append("These findings come from a manual review of a full trace set captured during development. The traces are not kept in the repo, but the behavioral pattern was stable across runs.")
    lines.append("")
    for finding in QUALITATIVE_FINDINGS:
        lines.append(f"- {finding}")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- `total_tokens` comes from provider usage fields.")
    lines.append("- `tool_output_tokens` is estimated from tool-result payload text with the configured tokenizer.")
    lines.append("- Tool descriptions, system prompts, and other non-tool context are reflected only in `total_tokens`, not in `tool_output_tokens`.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the overlap benchmark and write a markdown report.")
    parser.add_argument("--prompts", default="token_efficiency/prompts.yaml", help="Path to prompts YAML")
    parser.add_argument("--report", default="token_efficiency/report.md", help="Output markdown report")
    parser.add_argument("--approach", choices=["skill", "mcp", "both"], default="both")
    parser.add_argument("--scenario", help="Single scenario id or comma-separated list")
    parser.add_argument("--repeats", type=int, help="Override repeats per prompt")
    parser.add_argument("--model", default=os.getenv("BENCHMARK_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    args = parser.parse_args()

    _ensure_env()

    prompts_path = Path(args.prompts).resolve()
    report_path = Path(args.report).resolve()
    config = load_prompts(prompts_path)
    repeats = args.repeats if args.repeats is not None else config.repeats_per_scenario
    selected = {part.strip() for part in args.scenario.split(",") if part.strip()} if args.scenario else None
    scenarios = _select_scenarios(config.scenarios, selected)
    approaches = _approaches(args.approach)

    total_runs = len(scenarios) * len(approaches) * repeats
    run_number = 0
    failures = 0
    results: list[dict] = []

    print(
        json.dumps(
            {
                "model": args.model,
                "approaches": approaches,
                "scenarios": [scenario.scenario_id for scenario in scenarios],
                "repeats": repeats,
                "total_runs": total_runs,
                "report": str(report_path),
            },
            indent=2,
        )
    )

    for approach in approaches:
        for scenario in scenarios:
            for run_index in range(1, repeats + 1):
                run_number += 1
                print(f"[{run_number}/{total_runs}] approach={approach} scenario={scenario.scenario_id} run={run_index}")
                result = collect_trace(
                    scenario=scenario,
                    approach=approach,
                    model=args.model,
                    run_index=run_index,
                    max_steps=args.max_steps,
                    temperature=args.temperature,
                )
                results.append(result)
                print(
                    f"  -> {result['status']} total_tokens={result['metrics']['total_tokens']} turns={result['metrics']['total_turns']}"
                )
                if result["status"] != "success":
                    failures += 1
                time.sleep(max(0.0, args.sleep_seconds))

    summaries = _collect_summaries(results)
    report = _render_report(results=results, summaries=summaries, model=args.model, prompts_path=prompts_path)
    report_path.write_text(report, encoding="utf-8")

    print(f"Wrote report: {report_path}")
    print(f"Run complete. failures={failures} / {total_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
