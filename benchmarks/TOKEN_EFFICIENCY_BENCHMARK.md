# Token Efficiency Benchmark: Readwise Skill vs Official Readwise MCP

## Motivation

The official Readwise MCP (`@readwise/readwise-mcp@0.0.7`) exposes a **single tool** — `search_readwise_highlights` — that performs vector + full-text search and returns raw JSON. This skill provides **two focused CLIs** covering highlights CRUD, books, documents, daily review, and more, with structured output and field selection.

The hypothesis is that the skill's CLI-based approach is significantly more token-efficient because:
1. **Compact output** — field selection (`--fields`) and formatted rendering vs full JSON blobs
2. **Targeted commands** — the agent calls `highlights list --tag philosophy --fields text,note` instead of receiving every field and filtering mentally
3. **SKILL.md guidance** — agents get concise, structured docs vs opaque MCP tool schemas
4. **No round-trip bloat** — MCP tool calls carry JSON-RPC framing; CLI calls are plain text

This benchmark quantifies those differences under realistic usage patterns.

---

## Design Principles

| Principle | Detail |
|---|---|
| **Realistic tasks** | Scenarios drawn from actual Readwise power-user workflows |
| **Apples-to-apples** | Same underlying API data; same task goal; measure total tokens consumed by the agent to complete |
| **Reproducible** | Stub server provides deterministic data; no live API dependency |
| **Multi-dimensional** | Measure input tokens, output tokens, tool-call tokens, and total turns separately |

---

## What We Measure

### Primary Metric: Total Token Cost

For each scenario, measure:

| Metric | Description |
|---|---|
| `tool_schema_tokens` | One-time cost of tool/skill definitions injected into context |
| `tool_input_tokens` | Tokens in the agent's tool-call arguments (per turn) |
| `tool_output_tokens` | Tokens in tool results returned to the agent (per turn) |
| `agent_reasoning_tokens` | Tokens the agent generates to reason/plan (per turn) |
| `total_turns` | Number of agent ↔ tool round-trips to complete the task |
| `total_tokens` | Sum across all turns |

### Secondary Metrics

| Metric | Description |
|---|---|
| `task_success` | Did the agent achieve the goal? (boolean) |
| `latency_ms` | Wall-clock time to complete |
| `error_recovery_turns` | Extra turns caused by errors or retries |

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

### Tier 2 — Write Operations

#### S5: Create a highlight from a quote
> "Save this highlight: 'The obstacle is the way' from The Obstacle Is the Way by Ryan Holiday, tagged with stoicism and philosophy"

- **MCP path**: Not supported — MCP is read-only
- **Skill path**: `highlight create --text "The obstacle is the way" --title "The Obstacle Is the Way" --author "Ryan Holiday" --tags stoicism,philosophy`

#### S6: Bulk highlight creation
> "I have 5 quotes from this podcast episode I want to save" (agent given list)

- **MCP path**: Not supported
- **Skill path**: 5× `highlight create` calls or NDJSON bulk import

#### S7: Update a highlight's note
> "Add a note to highlight 12345: 'This connects to the idea of amor fati'"

- **MCP path**: Not supported
- **Skill path**: `highlight update 12345 --note "This connects to the idea of amor fati"`

### Tier 3 — Reader (Document Management)

#### S8: Save an article for later
> "Save this article to my reading list: https://example.com/article"

- **MCP path**: Not supported (MCP covers highlights only, not Reader)
- **Skill path**: `docs create --url https://example.com/article`

#### S9: Triage reading list
> "Show me my unread articles and move the first 3 to 'later'"

- **MCP path**: Not supported
- **Skill path**: `docs list --location new --category article --fields id,title` → 3× `docs update <id> --location later`

### Tier 4 — Multi-Step Workflows

#### S10: Research workflow
> "Find all my highlights about cognitive biases, then create a new highlight summarizing the top themes"

- **MCP path**: Search only; cannot create the summary highlight
- **Skill path**: `highlights list --tag cognitive-biases` → agent synthesizes → `highlight create --text "<summary>" --title "Cognitive Biases Summary" --tags cognitive-biases,synthesis --generated`

#### S11: Cross-reference workflow
> "Compare my highlights from Thinking Fast and Slow with those from Predictably Irrational"

- **MCP path**: Two `search_readwise_highlights` calls with `document_title` filters → two large JSON arrays → agent reasons over raw data
- **Skill path**: Two `highlights list --book-id <X> --fields text,note` calls → compact output → agent reasons over formatted text

---

## Implementation Plan

### Phase 1: Stub Infrastructure

Extend the existing stub server (`tests/stub_server/app.py`) to also mock the MCP search endpoint (`POST /api/mcp/highlights`). Seed both APIs with the same underlying dataset so results are comparable.

**Data corpus** (realistic scale):
- 50 books across 4 categories
- 500 highlights with tags, notes, locations
- 30 documents in Reader with mixed states

### Phase 2: Token Counting Harness

Build a lightweight harness that:

1. **Simulates agent execution** for each scenario under both approaches
2. **Counts tokens** using `tiktoken` (cl100k_base) for consistent measurement
3. **Records structured results** as JSON for analysis

```
benchmarks/
├── TOKEN_EFFICIENCY_BENCHMARK.md   ← this document
├── harness/
│   ├── __init__.py
│   ├── token_counter.py            ← tiktoken-based counting
│   ├── scenario_runner.py          ← executes scenarios, records metrics
│   ├── mcp_simulator.py            ← simulates MCP tool schema + responses
│   └── skill_simulator.py          ← simulates skill CLI schema + responses
├── scenarios/
│   ├── s01_search_topic.py
│   ├── s02_daily_review.py
│   ├── ...
│   └── s11_cross_reference.py
├── fixtures/
│   ├── corpus.json                 ← shared highlight/book/doc dataset
│   └── mcp_responses/              ← captured MCP-format responses
├── results/
│   └── .gitkeep
└── analyze.py                      ← generates comparison tables & charts
```

### Phase 3: Schema Cost Measurement

Measure the one-time context cost of each approach:

| Component | MCP | Skill |
|---|---|---|
| Tool definitions | MCP `tools/list` response JSON | SKILL.md content |
| Per-call framing | JSON-RPC envelope + Zod schema | CLI command string |

Tokenize the actual tool schemas and SKILL.md files to get exact numbers.

### Phase 4: Response Size Measurement

For each scenario, capture the tool output under both approaches and tokenize:

- **MCP**: Full `JSON.stringify(response.data.results)` — every field, no filtering
- **Skill**: CLI output with `--fields` selection and formatted rendering
- **Skill (--raw)**: CLI output with `--raw` for fair "full JSON" comparison

### Phase 5: End-to-End Simulation

For multi-step scenarios (S10, S11), simulate the full agent loop:
1. Agent sees task prompt
2. Agent selects tool/command
3. Tool returns result
4. Agent reasons and may call another tool
5. Repeat until task complete

Count tokens at every step. Compare total cost and number of turns.

### Phase 6: Analysis & Reporting

Generate:
- **Per-scenario comparison table** — tokens by category (schema, input, output, reasoning)
- **Aggregate summary** — mean/median savings across all scenarios
- **Capability coverage matrix** — which scenarios each approach can even handle
- **Breakdown charts** — where the savings come from (output compression, fewer turns, etc.)

---

## Expected Findings (Hypotheses)

| Hypothesis | Rationale |
|---|---|
| **50-70% output token reduction** on search scenarios | Field selection + formatting removes unused fields |
| **MCP cannot complete 7 of 11 scenarios** | Write ops, daily review, Reader are unsupported |
| **Lower turn count for filtered queries** | Skill's server-side filtering avoids agent post-processing |
| **Schema cost is comparable** | SKILL.md ≈ MCP tool definitions in size |
| **Multi-step workflows show largest gap** | Compounding savings per turn + capability gap |

---

## Running the Benchmark

```bash
# Install dependencies
cd benchmarks && uv sync

# Seed the corpus
uv run python harness/generate_corpus.py

# Run all scenarios
uv run python harness/scenario_runner.py --all --output results/run_$(date +%Y%m%d).json

# Generate report
uv run python analyze.py results/run_*.json --format markdown > results/REPORT.md
```

---

## Notes

- The official MCP source is `@readwise/readwise-mcp@0.0.7` (2.2kB, single file: `src/index.ts`)
- It exposes exactly one tool: `search_readwise_highlights(vector_search_term, full_text_queries[])`
- `full_text_queries` supports fields: `document_author`, `document_title`, `highlight_note`, `highlight_plaintext`, `highlight_tags`
- Responses are `JSON.stringify(response.data.results)` — unfiltered, unformatted
- The skill's two CLIs together cover ~20 distinct operations vs the MCP's 1
