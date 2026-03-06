# Token Efficiency Benchmark Report

Generated: 2026-03-06 01:46:53 UTC
Prompts: `prompts.yaml`
Model: `gpt-5.4-2026-03-05`
Tool token counter mode: `tiktoken`

## Overall

- `total_tokens` ratio (skill/mcp): `0.413`
- `tool_output_tokens` ratio (skill/mcp): `0.251`
- `total_turns` ratio (skill/mcp): `1.500`

`total_tokens` is the end-to-end measure for this harness: user prompt, system prompt, tool schema, tool-call arguments, tool results, and model output.
`tool_output_tokens` is diagnostic only: just the text returned from tools to the model. It does not include tool descriptions, system prompts, or full SKILL.md / MCP docs.
Those non-tool costs only appear inside `total_tokens` to the extent this harness actually injects them. This implementation uses minimal system prompts plus JSON tool schemas, not full SKILL.md.

## Token Shape

Approximate median-of-medians breakdown:

`skill` [======#######] other~1816 + tool~2078 = total~3893
`mcp`   [====############################] other~1124 + tool~8290 = total~9415

Legend: `=` non-tool tokens, `#` tool-result payload tokens

## Scenario Results

| Scenario | Skill success | MCP success | Skill total tok (med) | MCP total tok (med) | Total ratio | Skill tool out (med) | MCP tool out (med) | Out ratio | Skill turns (med) | MCP turns (med) | Turn ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| book_highlights_lookup | 5/5 | 5/5 | 4749.0 | 9336.0 | 0.509 | 2045.0 | 7388.0 | 0.277 | 2.0 | 1.0 | 2.000 |
| compound_filter_query | 5/5 | 5/5 | 3037.0 | 8848.0 | 0.343 | 2110.0 | 8026.0 | 0.263 | 1.0 | 1.0 | 1.000 |
| cross_reference_two_books | 5/5 | 5/5 | 5108.0 | 20317.0 | 0.251 | 2975.0 | 18541.0 | 0.160 | 2.0 | 1.0 | 2.000 |
| search_highlights_by_topic | 5/5 | 5/5 | 1003.0 | 9494.0 | 0.106 | 199.0 | 8555.0 | 0.023 | 1.0 | 1.0 | 1.000 |

## Scenario Token Shape

Each bar splits median total tokens into non-tool tokens (`=`) and tool-result payload tokens (`#`).

`book_highlights_lookup`
`skill` [========######] other~2704 + tool~2045 = total~4749
`mcp`   [======######################] other~1948 + tool~7388 = total~9336

`compound_filter_query`
`skill` [===#######] other~927 + tool~2110 = total~3037
`mcp`   [===#########################] other~822 + tool~8026 = total~8848

`cross_reference_two_books`
`skill` [===####] other~2133 + tool~2975 = total~5108
`mcp`   [==##########################] other~1776 + tool~18541 = total~20317

`search_highlights_by_topic`
`skill` [==#] other~804 + tool~199 = total~1003
`mcp`   [===#########################] other~939 + tool~8555 = total~9494

## Qualitative Findings

These findings come from a manual review of a full trace set captured during development. The traces are not kept in the repo, but the behavioral pattern was stable across runs.

- The skill traces are more procedural and easier to audit. For book tasks the model typically resolves a book first, then fetches highlights by `book_id`.
- The MCP traces are more one-shot. The model usually issues a broad search and then summarizes a large raw JSON payload, which reads smoothly but is less transparent to inspect.
- The clearest behavioral gap is constraint fidelity. In `compound_filter_query`, the skill path enforces both tag and recency. The MCP path cannot verify the recency constraint from the returned payload, so it falls back to a caveated partial answer.
- The skill path is better at entity disambiguation. In book-oriented scenarios it resolves concrete ids first; the MCP path relies on title search over the whole corpus.
- The MCP payload gives the model richer provenance, but also far more irrelevant structure. The skill payload is leaner and keeps the model focused, at the cost of less context.
- Across runs, the qualitative pattern was stable: skill answers were narrower and more literal; MCP answers were broader and more synthetic.

## Notes

- `total_tokens` comes from provider usage fields.
- `tool_output_tokens` is estimated from tool-result payload text with the configured tokenizer.
- Tool descriptions, system prompts, and other non-tool context are reflected only in `total_tokens`, not in `tool_output_tokens`.
- Recall is an important caveat. Some of the skill advantage here comes from returning a smaller evidence set, not just a more compact serialization of the same evidence. That is most likely in `cross_reference_two_books` and somewhat possible in `search_highlights_by_topic`, where the MCP path searched more broadly than the skill path.
