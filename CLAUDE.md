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
5. **Two artifacts: a sparse deck and a written memo.** (Revised 2026-07-29 — the previous rule
   required the *slide* to read cold, which drove the 07-27 weekly to 235 words/slide and made it
   read as narration notes rather than a presentation.) Split the job:
   - **The deck is for presenting.** Claim, number, figure, and a one-line takeaway — nothing else.
     Target **≤ 60 words/slide**; if a slide needs more to be understood, the surplus belongs in the
     memo. Prefer a figure or a matrix over a paragraph. Frame titles still follow rule #6.
   - **The word budget covers PROSE ONLY** (revised 2026-07-31). Tables, matrices and figures are
     exempt — a table may be as long and as dense as it needs to be, and a results table that mirrors
     a published one should mirror it *in full* rather than being trimmed to fit a word count.
     Counting table cells as words is what drove the 08-05 eval tables to be cut down to four
     columns when the point of them was to sit beside P-MAGIC's. When checking density, strip
     `tabular` bodies first and count what is left.
   - **The memo is for reading cold** (`presentation/centri-weekly-<date>-memo.md`). Prose, one page,
     written so the advisor can reconstruct every slide without the presenter: define each
     term/acronym on first use, replace internal shorthand (module / gate / function names, "seed",
     "manifest") with plain-language descriptions, and carry the caveats, retractions, and the "why"
     behind each number.
   - Every claim in the deck must appear in the memo; the memo may hold more than the deck shows.
   Check density before declaring done: `python3 - <<'EOF'` word-count per frame, or simply reread
   each slide asking whether it is a script or a visual aid.
6. **Short, regular frame titles.** `\frametitle` / `\begin{frame}{...}` is a plain slide title — a
   concise noun or verb phrase (e.g. "Verifying each measurement", "The accuracy limit: the marker"),
   *not* a full sentence. The sentence-style summary belongs in the one-line takeaway (rule #5), not
   in the title.
