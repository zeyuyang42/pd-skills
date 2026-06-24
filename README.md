# pd-skills

Reusable **Agent Skills** for audio / Pure&nbsp;Data development, in the portable `SKILL.md` format that works
across **Claude Code, Codex, GitHub Copilot CLI, Gemini CLI**, and other agent runtimes.

## Skills

| Skill | What it does |
|-------|--------------|
| [`pd-externals`](skills/pd-externals/) | Write, compile, and debug **C externals (plugins) for Pure Data** — the boilerplate, conventions, full API reference, the crash/corruption rules, and annotated control + signal (`~`) templates with a pd-lib-builder Makefile. |

## Install

### Quick: the installer

```bash
git clone https://github.com/zeyuyang42/pd-skills.git
cd pd-skills
./install.sh <agent> [skill]      # e.g. ./install.sh claude pd-externals
```

`<agent>` is one of `claude`, `codex`, `copilot`, `gemini`, or `agents` (the cross-runtime path). Omit the
skill name to install all skills. Add `--link` to symlink instead of copy (repo edits propagate), or
`--dest DIR` to install somewhere custom.

### Manual: copy the folder

A skill is just a folder — copy `skills/<name>/` into your agent's skills directory:

| Agent | Skills directory | Command |
|-------|------------------|---------|
| Claude Code | `~/.claude/skills/` | `cp -R skills/pd-externals ~/.claude/skills/` |
| Codex | `~/.codex/skills/` (or `~/.agents/skills/`) | `cp -R skills/pd-externals ~/.codex/skills/` |
| GitHub Copilot CLI | `~/.copilot/skills/` (or `~/.agents/skills/`) | `cp -R skills/pd-externals ~/.copilot/skills/` |
| Gemini CLI | `~/.gemini/skills/` (or `~/.agents/skills/`) | `cp -R skills/pd-externals ~/.gemini/skills/` |
| Codex / Copilot / Gemini (shared) | `~/.agents/skills/` | `cp -R skills/pd-externals ~/.agents/skills/` |

`~/.agents/skills/` is a cross-runtime path shared by Codex, Copilot CLI, and Gemini CLI — install once there
to cover all three.

### One file: the `.skill` bundle

Each skill is also packaged as a `.skill` zip in [`dist/`](dist/). Download one and unzip it into any skills
directory:

```bash
unzip pd-externals.skill -d ~/.claude/skills/      # creates ~/.claude/skills/pd-externals/
```

After installing, restart/reload your agent if needed, then ask it something the skill covers (e.g. *"write a
Pure Data signal external in C that …"*) and it will consult the skill.

> **Note on one-command marketplace installers.** Some runtimes can install straight from a GitHub repo (e.g.
> `gemini extensions install <url>`, or a Codex/Copilot marketplace add). Those require the repo to be
> **public or authenticated**. While this repo is private, use the installer, a manual copy, or the `.skill`
> bundle above — all work offline.

## Repo layout

```
pd-skills/
├── skills/<name>/          # each skill: SKILL.md (+ references/, assets/)
├── dist/<name>.skill       # prebuilt zip of each skill
├── install.sh              # copy/symlink a skill into an agent's skills dir
└── scripts/package.sh      # rebuild dist/*.skill from skills/ (needs only `zip`)
```

## Adding or updating a skill

1. Create `skills/<name>/SKILL.md` (plus `references/` / `assets/` as needed).
2. Run `bash scripts/package.sh` to (re)build `dist/<name>.skill`.
3. Commit.

## License

Tooling and templates are **MIT** (see [LICENSE](LICENSE)). The `pd-externals` skill is distilled from the
[Pure Data externals HOWTO](https://github.com/pure-data/externals-howto) — see [NOTICE](NOTICE) for
attribution.
