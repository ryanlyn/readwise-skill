# readwise-skill

A plugin for using [Readwise](https://readwise.io) and [Reader](https://readwise.io/read) in your AI agents. Works with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Claude Desktop, and [OpenAI Codex](https://github.com/openai/codex).

Shines when working across your entire library - extracting quotes from transcripts, saving generated highlights across multiple sources, triaging your inbox, connecting highlights across books.

## What you can do

`Save the best quote from this transcript` - paste a transcript, article, or notes and ask Claude to extract and save the best parts:
```
> Here's a transcript from Grady Booch's interview. Save the best quote.

Done. Saved to Readwise:
  "The main thing that constrains us in software is our imagination...
   Think of it as an opportunity. It's not a loss."
  — Grady Booch
```

`What are my latest unread Reader docs?`
```
> What are my latest unread Reader docs?

| Title                                          | Source           | Words | Progress |
|------------------------------------------------|------------------|------:|:--------:|
| Does AI already have human-level intelligence? | nature.com       | 2,374 |    0%    |
| Interpretability vs Neuroscience               | colah.github.io  | 1,394 |    0%    |
| On neural scaling and the quanta hypothesis    | ericjmichaud.com | 9,976 |    0%    |

... (7 more)
```

The basics work as you'd expect - search highlights, daily review, save articles. The interesting part is what becomes possible when your agent can read and write across your whole library:

`Save this to Reader, get the transcript, suggest quotes, save them to Readwise, and archive` - all in one conversation:
```
> Save this to Reader: https://www.youtube.com/watch?v=OfMAtaocvJw
Done. Saved "The third golden age of software engineering" to Reader.

> Get the transcript and suggest the most surprising quotes
Here are 3 quotes that challenge conventional thinking:
1. "Fear not, O developers. Your tools are changing, but your problems are not."
2. "We're not going to have fewer software engineers - we're going to have
    more, doing things we couldn't imagine"
3. ...

> Save #1 and #2 to Readwise, then archive the video
Done. Saved 2 highlights to Readwise and archived the document in Reader.
```

`What are my latest RSS articles? Rank by novelty` - triage your feed, then save what matters:
```
> What are my latest RSS articles? Rank by novelty.

High novelty:
- The Yodogo Hijacking (historical narrative)
- My Enemy, The Leitmotif (music/aesthetics critique)
- The Church Of Interruption (attention/tech critique)

Low novelty:
- How Transformers Architecture Powers Modern LLMs
- A Guide to Effective Prompt Engineering

> Save #1 and #2 to Readwise
Done. Saved 2 highlights to Readwise.
```

Build on what you've read - generate visualizations, interactive demos, or cross-book analysis from your library:

`Visualise the main themes as overlapping timelines in the article, ascii` - from a Paul Graham essay saved in Reader:

<img src="assets/how-to-do-great-work.png" alt="ASCII theme timeline of Paul Graham's How to Do Great Work" width="600">

`Now animate each theme entering and exiting over the essay's structure`:

https://github.com/ryanlyn/readwise-skill/raw/main/assets/when-to-do-what-you-love.mp4

```
> Pull my highlights from "Thinking in Systems" and create an Excalidraw
  diagram of the key feedback loops

> Build me an interactive HTML demo of the reinforcing loops from chapter 3
  using my highlights as source material

> Compare my highlights from "Meditations" and "Letters from a Stoic" -
  where do Aurelius and Seneca agree? Where do they diverge?
```

## Getting started

```
/plugin marketplace add ryanlyn/readwise-skill
/plugin install readwise@readwise-skill
```

Set your Readwise access token (find it at https://readwise.io/access_token):
```
export READWISE_TOKEN=<your-token>
```

Or store it as a Claude Code secret so it persists across sessions.

Verify by asking Claude *"Validate my Readwise token"*.

## Capabilities

**Readwise** - list books, search/create/update/delete highlights, daily review, bulk import via NDJSON

**Reader** - list/save/archive documents, pull recent updates, triage inbox by location and category

Both skills support:
- `--dry-run` to preview any write operation before executing
- `--raw` for full JSON output
- Rate limits: 60 req/min (Readwise), 20 req/min (Reader)

## Privacy & data

Your Readwise access token grants full read/write access to your account. This plugin only communicates with `readwise.io` API endpoints - no data is sent anywhere else. Destructive operations (`highlight delete`) prompt for confirmation. Use `--dry-run` to preview payloads before any write.

## Uninstall

```
/plugin uninstall readwise@readwise-skill
```

## Codex installation

Codex skill zips are published as CI artifacts on each push to `main`. Download the latest from the [Actions tab](https://github.com/ryanlyn/readwise-skill/actions) or build from source.

Install one or both skills (they work independently):

```bash
VERSION="0.1.0"  # check CI artifacts for latest
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
unzip -o "readwise-${VERSION}.zip" -d "$CODEX_HOME/skills"
unzip -o "readwise-reader-${VERSION}.zip" -d "$CODEX_HOME/skills"
```

Codex looks for skills in `$CODEX_HOME/skills/` (default `~/.codex/skills/`). Start a new Codex session after installing, then verify:

```
Validate my Readwise token
```

## Development

Plugin source lives in `plugins/readwise/`.

```
cd plugins/readwise
uv sync --extra dev
uv run pytest tests/ -v
```

Tests use a local stub server that mocks both APIs - no real token needed.

Build Codex zip artifacts locally:

```bash
python3 scripts/build_codex_dist.py --clean
```

Verify artifacts before publishing:

```bash
scripts/verify_codex_dist.sh
```

## License

[MIT](LICENSE)
