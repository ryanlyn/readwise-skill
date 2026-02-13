# readwise-skill

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin for automating [Readwise](https://readwise.io) workflows — syncing highlights, managing documents, and streamlining your reading pipeline.

## Getting started

```
/plugin marketplace add ryanlyn/readwise-skill
/plugin install readwise@readwise-skill
```

Set your token from https://readwise.io/access_token:
```
export READWISE_TOKEN=<your-token>
```

Verify by asking Claude *"Validate my Readwise token"*.

## Codex installation

Install both skills from zip artifacts:

1. Get the zip files (`readwise-<version>.zip` and `readwise-reader-<version>.zip`).
2. Unzip them into your Codex skills directory.
3. Restart Codex.
4. Ask Codex to run a quick auth check.

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
unzip -o readwise-<version>.zip -d "$CODEX_HOME/skills"
unzip -o readwise-reader-<version>.zip -d "$CODEX_HOME/skills"
ls "$CODEX_HOME/skills/readwise/SKILL.md" "$CODEX_HOME/skills/readwise-reader/SKILL.md"
```

After restarting Codex, run:

```
Validate my Readwise token
```

### Build from source (maintainers)

Build the Codex zip artifacts locally:

```bash
python3 scripts/build_codex_dist.py --clean
```

Verify artifacts before publishing:

```bash
scripts/verify_codex_dist.sh
```

## What you can do

**Readwise** — query highlights, save quotes, daily review

**Reader** — check your reading list, save articles, triage inbox

```
> Save this to Reader: https://www.youtube.com/watch?v=OfMAtaocvJw
Done. Saved "The third golden age of software engineering" to Reader.

> Get the transcript and suggest the most surprising quotes
Here are 3 quotes that challenge conventional thinking:

1. "Fear not, O developers. Your tools are changing, but
    your problems are not."
2. "We're not going to have fewer software engineers - we're going to have more, doing things we couldn't imagine"
3. ...

> Save #1 and #2 to Readwise, then archive the video
Done. Saved 2 highlights to Readwise and archived the document in Reader.
```

```
> What are my latest RSS articles? Rank by novelty.

High novelty:
- The Yodogo Hijacking (historical narrative)
- My Enemy, The Leitmotif (music/aesthetics critique)
- The Church Of Interruption (attention/tech critique)

Low novelty:
- How Transformers Architecture Powers Modern LLMs
- A Guide to Effective Prompt Engineering

> Summarize "The Yodogo Hijacking" and suggest the most important quotes

The article covers the 1970 hijacking of Japan Airlines Flight 351 by
members of the Japanese Red Army who demanded to be flown to North Korea.

Key quotes:
1. "They spent the next 50 years in Pyongyang, living as propaganda
    tools for a regime they no longer believed in."
2. "The youngest hijacker was 16. He would not see Japan again
    until he was 67."
3. ...

> Save #1 and #2 to Readwise
Done. Saved 2 highlights to Readwise.
```

## Examples

### Readwise

Query your highlights:
```
> Find my highlights from Meditations

Found Meditations by Marcus Aurelius (95 highlights). Here are a few:

> The things you think about determine the quality of your mind.
  Your soul takes on the color of your thoughts.

> The impediment to action advances action. What stands in the way becomes the way.

... (93 more)
```

Save quotes from any source — paste a transcript, article, or notes and ask Claude to extract and save the best parts:
```
> Here's a transcript from Grady Booch's interview. Save the best quote.

Done. Saved to your Readwise:
- text="The main thing that constrains us in software is our imagination...
  Think of it as an opportunity. It's not a loss."
  author="Grady Booch", tags=[generated]
```

### Reader

Check your reading list:
```
> What are my latest unread Reader docs?

| Title                                          | Source                 | Words | Progress |
|------------------------------------------------|------------------------|------:|:--------:|
| Does AI already have human-level intelligence? | nature.com             | 2,374 |    0%    |
| Interpretability vs Neuroscience               | colah.github.io        | 1,394 |    0%    |
| On neural scaling and the quanta hypothesis    | ericjmichaud.com       | 9,976 |    0%    |

... (7 more)
```

Save articles for later:
```
> Save this URL to Reader: https://example.com/article

Done. Saved to Reader with id=01abc123...
```

## Development

Plugin source lives in `plugins/readwise/`.

```
cd plugins/readwise
uv sync --extra dev
uv run pytest tests/ -v
```

Tests use a local stub server that mocks both APIs — no real token needed.

## License

[MIT](LICENSE)
