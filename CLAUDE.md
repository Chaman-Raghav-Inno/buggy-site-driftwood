# CLAUDE.md: buggy-site-driftwood (Driftwood Stays)

- The bugs in this site are **planted on purpose**; BUGS.md is the answer key. Never fix a planted bug unless asked
  to, and keep BUGS.md, the tests and the code in step when a bug is added, changed or removed.
- Nothing served (`driftwood/pages/`, `driftwood/static/`) may name or hint at a bug: no `BUG-nn` markers, comments or
  file names there. Server-side Python may carry `BUG-nn` comments.
- The rules the bugs break are published on `/help` and the listing page; keep them accurate.
- Avoid unplanned bugs (console errors, broken layout on phones, races on slow networks): they blur what the scanner
  found. Pages ignore clicks until their data has loaded (`is-loading` in `core.js`); keep it that way.

## Validation (before declaring done)

```bash
ruff check .
ruff format --check .
pytest -q
```
