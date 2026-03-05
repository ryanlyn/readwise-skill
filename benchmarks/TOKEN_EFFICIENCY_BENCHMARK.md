# Token Efficiency Benchmark: Readwise Skill vs Official Readwise MCP

## Motivation

The official Readwise MCP (`@readwise/readwise-mcp@0.0.7`) exposes a **single tool** — `search_readwise_highlights` — that performs vector + full-text search and returns raw JSON. This skill provides **two focused CLIs** covering highlights CRUD, books, documents, daily review, and more, with structured output and field selection.

The hypothesis is that the skill's CLI-based approach is significantly more token-efficient because:
1. **Compact output** — field selection (`--fields`) and formatted rendering vs full JSON blobs
2. **Targeted commands** — the agent calls `highlights list --tag philosophy --fields text,note` instead of receiving every field and filtering mentally
3. **SKILL.md guidance** — agents get concise, structured docs vs opaque MCP tool schemas
4. **No round-trip bloat** — MCP tool calls carry JSON-RPC framing; CLI calls are plain text

This benchmark quantifies those differences under realistic usage patterns, using your real Readwise library.

---

## Approach

Run each scenario **live** against the real Readwise API under both approaches. Capture full agent traces (tool schemas, tool calls, tool results, agent reasoning) and compute token metrics from the traces.

- **Real data only** — your actual Readwise library, no synthetic corpus
- **Write ops use `--dry-run`** — no side effects; we still capture the full payload the agent would send
- **Live agent traces** — run each scenario through Claude API to get real reasoning token counts, not estimates
- **Single operator** — designed for you to run locally; no CI/mock/replay infrastructure

---

## What We Measure

### Per-Trace Metrics

| Metric | Description |
|---|---|
| `tool_schema_tokens` | One-time cost of tool/skill definitions injected into context |
| `tool_input_tokens` | Tokens in the agent's tool-call arguments (summed across turns) |
| `tool_output_tokens` | Tokens in tool results returned to the agent (summed across turns) |
| `reasoning_tokens` | Tokens the agent generates to think/plan/respond (summed across turns) |
| `total_turns` | Number of agent ↔ tool round-trips to complete the task |
| `total_tokens` | Grand total from API usage fields |
| `task_success` | Did the agent achieve the goal? (boolean) |

### Derived Comparisons

| Comparison | Formula |
|---|---|
| **Output compression ratio** | `skill_tool_output_tokens / mcp_tool_output_tokens` |
| **Total cost ratio** | `skill_total_tokens / mcp_total_tokens` |
| **Turn efficiency** | `skill_total_turns / mcp_total_turns` |
| **Capability coverage** | Scenarios completable by each approach |

---

## Scenarios

### Tier 1 — Read-Heavy (most common Readwise usage)

#### S1: Search highlights by topic
> "Find my highlights about stoicism"

- **MCP path**: `search_readwise_highlights` with `vector_search_term: "stoicism"` → raw JSON array
- **Skill path**: `highlights list --tag stoicism --fields text,title,note` → compact formatted output

#### S2: Get today's daily review
> "Show me my daily review highlights"

- **MCP path**: Not supported — agent must explain it cannot do this, or attempt workaround
- **Skill path**: `highlights review` → formatted highlight cards

#### S3: Look up a specific book's highlights
> "Show me all highlights from Meditations by Marcus Aurelius"

- **MCP path**: `search_readwise_highlights` with `full_text_queries: [{field_name: "document_title", search_term: "Meditations"}, {field_name: "document_author", search_term: "Marcus Aurelius"}]` → raw JSON
- **Skill path**: `books --title "Meditations" --author "Marcus Aurelius"` → get book_id → `highlights list --book-id <id> --fields text,note,location`

#### S4: Search highlights with compound filters
> "Find highlights I tagged 'key-insight' from articles updated in the last week"

- **MCP path**: `search_readwise_highlights` with `full_text_queries: [{field_name: "highlight_tags", search_term: "key-insight"}]` → raw JSON (no date filter, no category filter — agent must post-filter)
- **Skill path**: `highlights list --tag key-insight --category articles --updated-after 2026-02-26 --fields text,title,note`

### Tier 2 — Write Operations (--dry-run)

#### S5: Create a highlight from a quote
> "Save this highlight: 'The obstacle is the way' from The Obstacle Is the Way by Ryan Holiday, tagged with stoicism and philosophy"

- **MCP path**: Not supported — MCP is read-only
- **Skill path**: `highlight create --text "The obstacle is the way" --title "The Obstacle Is the Way" --author "Ryan Holiday" --tags stoicism,philosophy --dry-run`

#### S6: Bulk highlight creation
> "I have 5 quotes from this podcast episode I want to save" (agent given list)

- **MCP path**: Not supported
- **Skill path**: 5× `highlight create ... --dry-run` calls

#### S7: Update a highlight's note
> "Add a note to highlight 12345: 'This connects to the idea of amor fati'"

- **MCP path**: Not supported
- **Skill path**: `highlight update 12345 --note "This connects to the idea of amor fati" --dry-run`

### Tier 3 — Reader (Document Management)

#### S8: Save an article for later
> "Save this article to my reading list: https://example.com/article"

- **MCP path**: Not supported (MCP covers highlights only, not Reader)
- **Skill path**: `docs create --url https://example.com/article --dry-run`

#### S9: Triage reading list
> "Show me my unread articles and move the first 3 to 'later'"

- **MCP path**: Not supported
- **Skill path**: `docs list --location new --category article --fields id,title` → 3× `docs update <id> --location later --dry-run`

### Tier 4 — Multi-Step Workflows

#### S10: Research workflow
> "Find all my highlights about cognitive biases, then create a new highlight summarizing the top themes"

- **MCP path**: Search only; cannot create the summary highlight
- **Skill path**: `highlights list --tag cognitive-biases` → agent synthesizes → `highlight create --text "<summary>" --title "Cognitive Biases Summary" --tags cognitive-biases,synthesis --generated --dry-run`

#### S11: Cross-reference workflow
> "Compare my highlights from Thinking Fast and Slow with those from Predictably Irrational"

- **MCP path**: Two `search_readwise_highlights` calls with `document_title` filters → two large JSON arrays → agent reasons over raw data
- **Skill path**: Two `highlights list --book-id <X> --fields text,note` calls → compact output → agent reasons over formatted text

---

## Implementation

### Structure

```
benchmarks/
├── TOKEN_EFFICIENCY_BENCHMARK.md   ← this document
├── run_benchmark.py                ← main entry point
├── trace_collector.py              ← runs scenario through Claude API, captures full trace
├── analyze.py                      ← computes metrics from traces, generates report
├── scenarios.yaml                  ← scenario definitions (prompt, approach, expected commands)
└── traces/                         ← captured trace output (gitignored)
    ├── skill/
    │   ├── s01_search_topic.json
    │   └── ...
    └── mcp/
        ├── s01_search_topic.json
        └── ...
```

### Trace Collector

For each scenario, `trace_collector.py`:

1. Constructs a system prompt with either:
   - **Skill approach**: SKILL.md content + CLI tool definitions
   - **MCP approach**: MCP `tools/list` schema (captured once from the real MCP server)
2. Sends the scenario prompt to the Claude API
3. Executes tool calls live:
   - **Skill**: runs CLI commands against real Readwise API (with `--dry-run` for writes)
   - **MCP**: forwards to the real MCP server (for the 4 scenarios it supports)
4. Loops until the agent completes the task
5. Saves the full trace (all messages, tool calls, tool results, API usage per turn)

### Analyzing Traces

`analyze.py` reads saved traces and computes:

- Token counts per category from the API's `usage` response fields (exact, not estimated)
- Turn counts
- Success/failure
- Generates a markdown comparison table

### Running

```bash
# Ensure READWISE_TOKEN and ANTHROPIC_API_KEY are set

# Collect traces for all scenarios under both approaches
uv run python benchmarks/run_benchmark.py --approach both

# Collect traces for a single scenario
uv run python benchmarks/run_benchmark.py --scenario s01 --approach skill

# Analyze and generate report
uv run python benchmarks/analyze.py benchmarks/traces/ --format markdown
```

---

## Expected Findings (Hypotheses)

| Hypothesis | Rationale |
|---|---|
| **50-70% tool output token reduction** on search scenarios | Field selection + formatting removes unused fields |
| **MCP cannot complete 7 of 11 scenarios** | Write ops, daily review, Reader are unsupported |
| **Lower turn count for filtered queries** | Skill's server-side filtering avoids agent post-processing |
| **Real reasoning tokens higher for MCP** | Agent spends more tokens parsing raw JSON, extracting relevant fields |
| **Multi-step workflows show largest total gap** | Compounding savings per turn + capability gap |

---

## Notes

- The official MCP source is `@readwise/readwise-mcp@0.0.7` (2.2kB, single file: `src/index.ts`)
- It exposes exactly one tool: `search_readwise_highlights(vector_search_term, full_text_queries[])`
- `full_text_queries` supports fields: `document_author`, `document_title`, `highlight_note`, `highlight_plaintext`, `highlight_tags`
- Responses are `JSON.stringify(response.data.results)` — unfiltered, unformatted
- The skill's two CLIs together cover ~20 distinct operations vs the MCP's 1
- Scenario prompts should use books/tags that actually exist in your library — update `scenarios.yaml` accordingly
