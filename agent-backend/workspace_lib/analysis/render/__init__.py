"""Seeded reference rendering for the annotation subagent.

`annotate.py` is a vetted, deterministic implementation of the annotated-video
overlay. The video-annotation subagent (still an LLM subagent — see
`.pi/agent/agents/video-annotation-subagent.md`) is pointed at it as a reference
to run or lightly adapt, instead of authoring the overlay from scratch with the
hardcoded example numbers the old prompt embedded.

Pedagogy rule it embodies: label variables by SYMBOL only (`r`, `v`, `ac`, `w`)
with a definitions legend, and NEVER overlay numeric values — students measure and
reason rather than read answers off the frame.

(The figures subagent remains prompt-driven; no frozen figures module is seeded.)
"""
