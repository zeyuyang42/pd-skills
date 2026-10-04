# pd-skills

[Agent Skills](https://agentskills.io) for Pure&nbsp;Data development, in the portable `SKILL.md` format. They work in
Claude Code, Claude.ai, Codex, GitHub Copilot, Gemini CLI, Cursor, OpenCode, and other runtimes that read `SKILL.md`.

| Skill | What it does |
|-------|--------------|
| [`pd-externals`](skills/pd-externals/) | Write, compile, and debug **C externals for Pure Data**. Includes the conventions, the crash/corruption rules, an API reference with a guide to checking your own `m_pd.h`, and control and signal (`~`) templates with a pd-lib-builder Makefile. |

## Install

**Any agent, one command** (via [`skills`](https://github.com/vercel-labs/skills)):

```bash
npx skills add zeyuyang42/pd-skills --skill pd-externals        # project scope
npx skills add zeyuyang42/pd-skills --skill pd-externals -g     # user scope
```

**Native installers:**

| Runtime | Command |
|---------|---------|
| Claude Code | `/plugin marketplace add zeyuyang42/pd-skills`, then `/plugin install pd-externals@pd-skills` |
| GitHub Copilot | `gh skill install zeyuyang42/pd-skills pd-externals` |
| Gemini CLI | `gemini skills install https://github.com/zeyuyang42/pd-skills --path skills/pd-externals` |
| Claude.ai / desktop | Download [`dist/pd-externals.skill`](dist/), then go to *Customize › Skills › Upload a skill* |

**Manual copy.** A skill is just a folder. Copy `skills/pd-externals/` into one of these directories:

| Runtime | User | Project |
|---------|------|---------|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex, Gemini CLI, Copilot, Cursor, OpenCode | `~/.agents/skills/` | `.agents/skills/` |

Each runtime also reads its own directory (`~/.gemini/skills`, `~/.copilot/skills`, `~/.cursor/skills`,
`~/.config/opencode/skills`, `.github/skills`, …). The shared `.agents/skills` covers all of them at once.

**Offline installer** (copy, or `--link` to symlink):

```bash
git clone https://github.com/zeyuyang42/pd-skills.git && cd pd-skills
./install.sh <claude|codex|copilot|gemini|cursor|opencode|agents> [skill] [--link] [--dest DIR]
```

Once it's installed, ask something like *"write a Pure Data signal external in C that…"*. The agent loads the skill when the task matches.

## Evals

`evals/evals.json` defines 8 tasks: control and signal objects, a crash diagnosis, and trap cases such as outlet order,
the `CLASS_MAINSIGNALIN` float conflict, and per-instance state. `evals/grade_pd.py` checks each output's structure
and **compiles it against a real `m_pd.h`**. It finds the header through `$PD_INCLUDE`, `--pd-include`, or auto-detection.
`evals/trigger-evals.json` holds should/shouldn't-trigger queries.

```bash
python3 evals/grade_pd.py --eval-id 1 --run-dir path/to/run    # expects path/to/run/outputs/*.c
```

## Layout

```
skills/<name>/                 SKILL.md (+ references/, assets/)
dist/<name>.skill              prebuilt zip for upload
evals/                         tasks, grader, trigger cases
.claude-plugin/marketplace.json  Claude Code plugin marketplace
install.sh                     offline installer
scripts/package.sh             rebuild dist/*.skill (needs only `zip`)
```

To add or update a skill, edit `skills/<name>/` and run `bash scripts/package.sh`. For a new skill, also add it to `.claude-plugin/marketplace.json`.

## License

Tooling and templates are **MIT** (see [LICENSE](LICENSE)). `pd-externals` is distilled from the
[Pure Data externals HOWTO](https://github.com/pure-data/externals-howto); see [NOTICE](NOTICE).
