# seed

Content, not code. Baked into the image, so rebuild after editing.

| File | What | Read by |
|---|---|---|
| `routes.json` | Approved navigation routes: name -> `desc`, `path`, optional `choice` / `picks` / `wait_for_run` / `toggle_ax_key` | `app/tools/routes.py` at import (paths in open_setting's description; runnable routes to the executors) |

- **The schema and quirks:** `app/tools/README.md` (routes, dropdown `choice` blocks).
- **Menu paths go only in `routes.json`.** A `reference` entry (`"reference": true`, `"text"`) is a location Sol may state but can't queue.
- The KB (`problems.json`) was removed 10-17; a copy is in `~/Desktop/OLD Conductor/kb-2026-10-17/`.
- **After editing `routes.json`:** rebuild. Verify any new or changed path live in Logic Pro before trusting it, and ask the user to confirm menu paths against the running app rather than asserting them.
- **Dropdown `options` are copied from the running Logic** (the client's AX read or the user's screenshot), never guessed: guessed strings failed the client's choose and read-back.
