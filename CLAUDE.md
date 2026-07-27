# Centri — project notes for Claude

## Weekly presentation decks (`presentation/centri-*.tex`, Beamer / metropolis)

Going forward, **every weekly presentation must follow this treatment** (the five rules below).
Apply them when creating a new weekly deck and when editing an existing one.

1. **Current-state, not week-diffs.** Each slide reads as the current state of the work — it is all
   work-in-progress, presented as true *now*. No "last week we X / this week we Y", no "next week",
   no slide whose job is to address prior feedback, no dated callbacks ("yesterday's run", "last
   week's caveat"). Reframe "What changed this week" / "Done this week" into plain current-state
   statements.
2. **Cite study / method names, not people.** At most one attribution of a person; use the study
   names everywhere else — e.g. **SocioMathLLM** (LLM-judge + rubric Tables 8–10) and **Geo-QG**
   (AR-sensing + 3-tier) for the parent dissertation (Ika Utami); **P-MAGIC** for the sibling paper.
3. **Clean tables / matrices, not boxy stacked bands.** Prefer a who-scores-what matrix or a
   two-row transform table over stacked/side-by-side `tcolorbox` "bands". Use green checks (`\ok`)
   vs grey dashes, coloured headers, inline grey notes in the row label, and `\vfill` to centre
   vertically.
4. **Render-check before declaring done.** Compile twice (`pdflatex -interaction=nonstopmode`), then
   render each changed slide to PNG (`pdftoppm -f N -l N -r 150 -png deck.pdf /tmp/slide`) and eyeball
   it — watch for whitespace imbalance, bad wrapping, and information dropped in a redesign.
5. **Standalone / self-explanatory.** The deck must read cold — the advisor understands every slide
   from the slide alone, with no live narration. Define each term/acronym where it first appears,
   replace internal shorthand (module / gate / function names, "seed", "manifest") with plain-language
   descriptions, and give every slide an explicit one-line takeaway. Assume no spoken explanation and
   no reliance on the presenter or a prior slide.
6. **Short, regular frame titles.** `\frametitle` / `\begin{frame}{...}` is a plain slide title — a
   concise noun or verb phrase (e.g. "Verifying each measurement", "The accuracy limit: the marker"),
   *not* a full sentence. The sentence-style summary belongs in the one-line takeaway (rule #5), not
   in the title.
