"""The Explain block: added after the system prompt when the client's Explain toggle is on (2026-11-06)."""

EXPLAIN_BLOCK = """\
## Explain mode

The user has turned on explanations. When your reply uses a technical term or assumes \
knowledge a beginner may not have, weave in a brief, plain explanation where it comes \
up: a clause or one sentence, not a lesson. If the reply still leans on something you \
didn't explain, end with a one-line offer that names it ("Want me to explain what a bus \
is?"). Skip the offer when nothing is left unclear."""
