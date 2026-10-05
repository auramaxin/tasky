# tasky

A small, **human-readable command-line task manager**. Tasks live in a plain
text file you can read, edit, grep, sync, and version-control. `tasky` gives
that file a fast CLI: add tasks, organize them with priorities / projects /
contexts / due dates, then filter, search, sort, and report on them.

Built with the Python **standard library only** — no third-party dependencies.

```
$ tasky add "Ship v2 release" +work @office -P A --due 2026-09-19
Added #1: (A) 2026-09-21 Ship v2 release +work @office due:2026-09-19

$ tasky list --overdue
1 (A) Ship v2 release +work @office due:2026-09-19
-- 1 task(s)

$ tasky stats
tasky summary
  total       4
  pending     3
  done        1
  overdue     1
  completion  25%
  priorities  (A) 1, (C) 1
```

---

## Open-source reference project

**Primary reference:** todo.txt-cli
**GitHub URL:** https://github.com/todotxt/todo.txt-cli

This project was built to be **comparable in scope** to two well-known
open-source task managers, which were used only as *functional references*:

- **[todo.txt-cli](https://github.com/todotxt/todo.txt-cli)** — the primary
  reference; a shell program over the plain-text
  [`todo.txt` format](https://github.com/todotxt/todo.txt)
  (priorities `(A)`, `+projects`, `@contexts`, `key:value` tags).
- **[Taskwarrior](https://github.com/GothenburgBitFactory/taskwarrior)** — a
  secondary reference; a richer C++ task manager (filters, reports, due dates,
  urgency).

`tasky` deliberately reuses the *readable text convention* those tools made
popular so files stay interoperable, but **no code was copied**: the parser,
serializer, data model, query engine, storage layer, and CLI are all original
Python written for this project.

---

## AI tools used

This project was developed with the assistance of the following AI tool:

- **Claude Code** (Anthropic's agentic coding CLI/app), powered by the
  **Claude Opus 4.8** model.

The AI assistant was used to design the architecture, write the original
implementation (parser, data model, query engine, storage, and CLI), author
the unit tests, and produce this documentation. All generated code was built,
run, and verified (51 passing unit tests plus an end-to-end CLI walkthrough).

### Scope comparison

| Capability                         | todo.txt-cli | Taskwarrior | **tasky** |
|------------------------------------|:------------:|:-----------:|:---------:|
| Plain-text, human-readable store   | ✅ | partial (uses its own DB) | ✅ |
| Add / list / complete / edit / rm  | ✅ | ✅ | ✅ |
| Priorities `(A)`–`(Z)`             | ✅ | ✅ | ✅ |
| Projects `+p` & contexts `@c`      | ✅ | ✅ (tags) | ✅ |
| Due dates & overdue detection      | via add-ons | ✅ | ✅ |
| Filter / search / sort             | ✅ | ✅ | ✅ |
| Summary report / stats             | partial | ✅ | ✅ |
| Archive completed tasks            | ✅ | ✅ | ✅ |

---

## Three major functionalities

1. **Task lifecycle management** — `add`, `list`, `done` / `undone`, `edit`,
   `pri` (re-prioritize), and `rm`, with stable 1-based task numbers and an
   atomic, comment-preserving text store.
2. **Metadata & organization** — an original parser/serializer for priorities,
   `+project` and `@context` tags, `due:` dates, and creation/completion dates,
   plus `projects` / `contexts` listings.
3. **Querying & reporting** — a composable filter engine (project, context,
   priority, status, overdue, due-before), full-text `search`, multi-key
   `--sort`, a `stats` summary report, and `archive` to sweep completed tasks
   into a companion `done` file.

---

## Install / build

Requires Python ≥ 3.9. Run straight from the source tree — no install needed:

```bash
python -m tasky --help
```

Or build and install it as a real package with a `tasky` console command:

```bash
python -m pip install .        # installs the `tasky` entry point
# or build a distributable wheel:
python -m pip wheel . -w dist --no-deps
```

## Usage

```bash
tasky add "Buy milk" +home @errands --due 2026-10-01 -P B
tasky list                       # pending tasks (default)
tasky list --all --sort due      # everything, earliest due first
tasky list -p work --overdue     # overdue tasks in +work
tasky list --json                # machine-readable JSON (respects all filters)
tasky done 3                     # complete task #3
tasky pri 2 A                    # set priority; `tasky pri 2 -` clears it
tasky edit 2 "Buy oat milk +home"
tasky search milk                # full-text search across all tasks
tasky projects                   # list every +project
tasky stats                      # summary report
tasky report                     # per-project breakdown (pending/done/overdue)
tasky archive                    # move completed tasks to the done file
```

### Where tasks are stored

Resolved in order: the `--file/-f` option → the `$TASKY_FILE` environment
variable → `~/.tasky/tasks.txt`. `tasky path` prints the active file.

### The file format

One task per line; blank lines and `#` comments are preserved:

```
(A) 2026-09-21 Ship v2 release +work @office due:2026-09-19
x 2026-09-20 2026-09-18 Write release notes +work
Buy groceries +home @errands
```

`x ` marks completion, `(A)` is a priority, leading `YYYY-MM-DD` dates are
completion/creation dates, and `+project` / `@context` / `key:value` tags are
parsed out of the description.

## Tests

51 unit tests covering the parser, query engine, and CLI, using only the
stdlib `unittest`:

```bash
python -m unittest discover -s tests -v
```

## Project layout

```
tasky/
├── pyproject.toml        # packaging + `tasky` console entry point
├── README.md
├── tasky/
│   ├── model.py          # Task dataclass + original text parser/serializer
│   ├── core.py           # TaskList, Query filter engine, stats
│   ├── storage.py        # atomic load/save, archive file
│   ├── cli.py            # argparse CLI, colour output, commands
│   └── __main__.py       # `python -m tasky`
└── tests/                # unittest suite (model / core / cli)
```

## License

MIT — see [LICENSE](LICENSE).
