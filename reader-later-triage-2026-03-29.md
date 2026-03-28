# Reader "Later" Triage Report — 2026-03-29

**Total documents in `later`:** 100
**Documents with some reading progress:** 4
**Recommended for archive:** 23

---

## Category 1: Low-Signal Tweets (no text / clickbait)

These tweets were saved with summaries that say "This tweet contains no text" — meaning the thread content wasn't properly ingested, so you'd need to click through to X anyway. Combined with their lower signal-to-noise ratio, they're prime archive candidates.

| # | Title | Author | ID | Reason |
|---|-------|--------|----|--------|
| 1 | From "Reasoning" Thinking to "Agentic" Thinking | Junyang Lin | `01kmn5ayygwk2rrswnje9agw9s` | "No text" tweet; topic covered better by papers in your queue |
| 2 | Out Of Distribution | Rich | `01kkc1a5gh1afz3vmae7rt4fva` | "No text" tweet; no summary to evaluate |
| 3 | 8 rules Elon Musk learned from Polytopia | Courtne Marland | `01kjyjftbhmgndkb2j0qfw7em9` | "No text" tweet; clickbait framing |
| 4 | You Can Make a Fortune Trading | Ryan Scott (Horse) | `01kj2cscdcyy9ewkyhk8w8gwgw` | "No text" tweet; trading thread, off-topic |

---

## Category 2: Very Short Link-Posts (< 500 words, just pointing elsewhere)

These are essentially bookmarks-of-bookmarks — Simon Willison or similar bloggers linking to the actual content. You'd get more value going directly to the source.

| # | Title | Author | Words | ID | Reason |
|---|-------|--------|-------|----|--------|
| 5 | Quantization from the ground up | Simon Willison | 252 | `01kmnf8w3w1ct2dnzfncmvzk4z` | Link-post; save the actual Sam Rose interactive essay instead |
| 6 | Thoughts on slowing the fuck down | Simon Willison | 398 | `01kmkfhb030ffc3hd2tm5c1xb9` | Link-post to Mario Zechner's opinion piece |
| 7 | The Cold Start Trap | Information Project | 372 | `01kmbv1b0qagbv9n2h0kp56vgd` | Very short LW post, abstract-level only |
| 8 | Leveraging academia | Andrew Critch | 443 | `01kkv3cs5mk3wafd3jqamny4cb` | Published 2016, 443 words; advice about entering AI alignment field is significantly outdated |

---

## Category 3: Content Overlap (one subsumes the other)

These are cluster where reading one gives you ~80%+ of the value of both.

| # | Keep | Archive | ID to archive | Reason |
|---|------|---------|---------------|--------|
| 9 | "Harness design for long-running application development" (4702w, deeper) | "Effective harnesses for long-running agents" (2047w, overview) | `01kmmwkw1c1dv349hf31eqkdjw` | Same topic from Anthropic, saved same day. The longer piece is the detailed version; the shorter is the intro companion |
| 10 | "Training on Documents About Monitoring Leads To CoT Obfuscation" (5902w, primary research) | "Load-Bearing Obfuscation and Self-Jailbreaking CoT" (4098w) | `01kmm85kb939b0e0grq6nj2m1v` | Both cover CoT obfuscation during RL training. The Haskins et al. paper is the primary contribution; Graeme Ford's notes are derivative |
| 11 | "Reasoning Models Struggle to Control Their Chains of Thought" (885w, OpenAI collab, definitive) | "Investigating encoded reasoning in LLMs" (1698w, ARENA capstone) | `01kka84wzsc08cmr0vtc0n9dqq` | The Chen et al./OpenAI piece is the authoritative work; the ARENA capstone is a preliminary 1-week project exploring the same question |

---

## Category 4: Off-Topic for Core Interests (ML/AI safety/research taste)

These don't align with your staff ML engineer / independent researcher profile. Not bad content — just not the highest ROI for your reading time.

| # | Title | Author | ID | Topic |
|---|-------|--------|----|-------|
| 12 | London's Divide Was Called Character | Lauren Leek | `01kmnw47h5shbmrddbj29zmtrk` | UK socioeconomic geography |
| 13 | Is fever a symptom of glycine deficiency? | Benquo | `01kmbcd39xmc9vytyww2r2byzg` | Speculative health/biochemistry |
| 14 | The Secret Police Playbook | Christian Gläßel | `01kknjyhg818gr36rjb42kjntw` | Political commentary (DHS / authoritarianism) |
| 15 | 'Having' And 'Being' Modes Of Depression | The Browser | `01kmka9hfd6w6kv8f8dt0gcv31` | Psychology/linguistics of depression across English & French |
| 16 | Learning About Longevity | Aria Schrecker | `01kharn5xapcfv524xmq3ryaz5` | Biology/longevity (mole rats) |
| 17 | The tactical playbook for getting 20-40% more comp | Lenny/Jacob Warwick | `01kkrr22qh8wq3eyjs0dwa9nnm` | Salary negotiation podcast |

---

## Category 5: Stale or Marginal Content

| # | Title | Author | ID | Reason |
|---|-------|--------|----|--------|
| 18 | The Singularity Is Always Steep | Philip Winston | `01kmaeybpvqc8gsr879ffhzk1j` | Published 2010, 858 words. Short blog post arguing technological progress doesn't peak — interesting premise but very dated framing |
| 19 | The best way to become good at something - David Epstein | TED-Ed | `01kjy03pecrpdz2hkkwwwh82ga` | Generic TED-Ed video (Range thesis); you likely already know this material |
| 20 | 30 Years of Business Advice in 13 Minutes | Chamath | `01kjp3z4889q72g8pmxx9y3gm7` | Generic business advice video; low information density for time investment |
| 21 | Some things I noticed while LARPing as a grantmaker | Zach Stein-Perlman | `01kmdnjy974s4decme4yaa6m51` | EA grantmaking advice; niche unless you're evaluating grants |
| 22 | I've been working my way through this epic 7-hour interview... | Kyle Chan | `01kmae7dqk4s87b9166ayxfh6e` | Tweet summarizing someone else's Gemini summary of a 7hr interview. Triple-indirection — find the primary source if interested |
| 23 | You're absolutely right, Senator. I was being naive about the political reality. | Chris Datcu | `01kmbv1ax8pyj1a961wcetzzm3` | Provocative title but only 739w on LLM formal verification pipelines; the insight is thin |

---

## Documents to Definitely KEEP (high signal, on-topic, no overlap)

For context, here are the ones I'd flag as highest-priority reads from your queue:

- **"How to win a best paper award"** — Nicholas Carlini, 9556w. Research taste gold.
- **"The Artificial Self"** — Jan_Kulveit, 8656w. Deep work on AI identity/self-models.
- **"Harness design for long-running application development"** — Anthropic, 4702w. Directly relevant to your agent engineering.
- **"In-context learning of representations can be explained by induction circuits"** — Andy Arditi (you're 27% through). Keep going.
- **"The Brand Age"** — Paul Graham, 7656w. Classic PG essay.
- **"Taste for Makers"** — Paul Graham (42% through). Finish this one.
- **"How To Become A Mechanistic Interpretability Researcher"** — Neel Nanda, 16582w. Core reference.
- **"Censored LLMs as a Natural Testbed for Secret Knowledge Elicitation"** — 5303w. Novel methodology.
- **"Measuring the Dark Energy of AI Progress"** — NanoGPT progress analysis. Quantitative and interesting.
- **"Martian Interpretability Challenge"** — Core problems in interp. Meta-level framing.

---

## Summary

| Reason | Count | IDs |
|--------|-------|-----|
| Low-signal tweets | 4 | See Category 1 |
| Short link-posts | 4 | See Category 2 |
| Content overlap | 3 | See Category 3 |
| Off-topic | 6 | See Category 4 |
| Stale/marginal | 6 | See Category 5 |
| **Total recommended for archive** | **23** | |

**No documents were archived or deleted.** This is a report only — confirm which (if any) you'd like me to move to archive.
