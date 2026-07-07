# Centri — speaker narration

Spoken-style notes for `centri-end-to-end.pdf` — written the way you'd actually say it, not read it. Talk to these, don't recite them. ~20–25 min for the main talk.

> **Deck order (this version):** the talk now *opens on the pedagogy/evaluation story* (per the co-author's advice to "start at slide 20"). The measurement internals, validation cases and the contribution/headline are deferred to a **Backup** section after the Summary (under `\appendix`, so they're off the page count) — open them only if the prof asks how the system works. The three **black slides before the Summary** are an intentional blackout buffer to blank the projector.
>
> **Naming:** the prior sensor/IMU method is referred to only as **"the prior method"** in the deck — don't say its name on stage.

---

## Title — *Centri: from one video to physics and personalised pedagogy*
"The whole idea of Centri is this: you take one ordinary video of something spinning, and from just that we recover the full physics of the motion — and then turn it into learning material. I'll start at the output and the evaluation, since that's the heart of it, and if you want to see how the measurement actually works under the hood I've got that ready too."

# MAIN TALK

## 1 — From each case to grounded learning material (real, generated)
"Here's where measurement turns into teaching — and this is real generated learning material, not a mock-up. Notice the explanation follows the motion regime. For the steady bike it says the wheel turns at a constant rate, omega around 5, period 1.18 seconds — uniform circular motion. For the slowing turntable it explains that as omega falls the centripetal acceleration falls with it, because a_c goes as omega squared. And for the speeding-up fan it narrates the actual spin-up — omega from about 2 at one second to nearly 10 at seven seconds, a steady angular acceleration of 1.18. The non-uniform cases let the material teach angular acceleration from the phenomenon — something a steady spin, or a generic textbook, can't."

## SECTION — Method 2: Generation
## 2 — Grounded, multimodal learning-material generation
"Each scene gives us one authentic learning passage, written by the language model but grounded strictly in that scene's real numbers, in five sections: the scenario, the variables we measured, how they relate, what the video shows over time, and how to read the figures. The key is a deterministic seed — we hand the model the variables, the formula relations, and a time-anchored omega-of-t — so the prose is fluent but it never invents a number. And it's multimodal: the passage refers to the same image, graph, and table the figures provide."

## 3 — One scene, four modalities — the actual stimuli
"These are the real figures the material reads from, for one fan scene. The image version shows the geometry on the annotated frame; the graph shows the omega-of-t curve; the table lists the measured quantities; and the text states them inline. Same physics, four ways in — which is the whole point of the modality comparison."

## 4 — The pedagogy seam: material and interactive tutor
"One measurement feeds two different things. The learning material is fixed — same every time. The tutor is interactive, it adapts to the student's level and watches for misconceptions. And the bigger point underneath: the old sensor approach needed two captures, a photo and a gyro recording, and one video just gives you both — which is genuinely simpler for the learner."

## SECTION — Method 3: Evaluation
## 5 — Evaluation methodology — what we measure and how
"Evaluation has two halves, and I want to be precise about which one is actually done. The automatic half is *run*: BERTScore for relevance against an authentic reference — and here's the nice part, the reference is a real published textbook section, OpenStax College Physics 6.2, reorganized into our format, completely independent of our pipeline. The current relevance score is 0.840, and remarkably consistent across runs, about plus-or-minus two thousandths. The quality half is *designed but not yet run*: an LLM-as-judge for correctness and pedagogy, and a panel of ten teachers rating clarity, correctness, level and usefulness, with the usual reliability and significance stats. I'm flagging that honestly — so far we have relevance, not a quality verdict. And that ordering is deliberate: BERTScore only measures similarity, not teaching quality, which is exactly why the teachers and the judge sit on top of it."

## 6 — How the automatic score is computed
"Let me actually show how the score works. BERTScore embeds every word of our material and the reference with a model that understands context — so 'wheel' and 'tyre' come out close — then it matches each word to its best partner and averages those similarities into precision, recall, and an F1. We score the whole passage and also section by section. The section breakdown is telling: it's highest on 'how the variables relate', 0.855, which is exactly the formulas the textbook shares — and lower on our grounded sections, which is the value we add that a generic textbook simply doesn't have. Across the five runs the whole-passage score is 0.840. And to be clear about the reference: it's the published OpenStax section, reorganized into our five sections — not the raw PDF and not paraphrased — so the two line up section by section. One honest caveat: section 6.2 is *uniform* circular motion, so it doesn't cover the spin-up and slow-down cases — we'll add further references for the non-uniform content. Swapping in whatever reference my co-author prefers keeps the method identical."

## 7 — What is compared: our material vs. the reference (fan)
"This is the comparison made concrete, side by side for the fan. On the left is our generated material, grounded in the tracked clip — radius 0.44 metres, omega 6.59, a_c about 22 — and every number there comes from tracking the toy frame by frame. On the right is the gold reference, the OpenStax section, reorganized into the same five sections. Look at the 'how the variables relate' rows — they say almost the same thing, the same formulas, which is exactly why that section scores highest. Now the honest disclosure, because someone always asks: we don't diff the raw textbook PDF against our text. We took the authentic OpenStax section and reorganized it — not rewrote it — into our five sections so the two align section by section, and we did that *independently* of our generation. The give-away that it's not reverse-engineered: the textbook's 'over time' section is its own car-and-centrifuge worked examples, nothing to do with our fan numbers. And we report the whole-passage score too, not just the flattering sections, so it isn't selective. The sections that score lower — the scenario, reading the figures — are precisely the grounded parts a generic textbook can't supply, which is our value-add, not a weakness."

## 8 — Automatic evaluation results — learning material
"Here are the actual numbers, laid out the way the prior method reports theirs. On the whole passage, against the OpenStax section, we get a BERTScore precision of 0.837, recall of 0.842, and an F1 of 0.840 — and that F1 is steady to about two thousandths across all five runs, which are three distinct phenomena, the turntable filmed three times. Diversity sits at 0.204, deliberately low because every passage is the same topic with the same structure. Their table also carries an LSTM fluency score; that one uses the prior method's own trained model, which I don't have, so rather than fake a non-comparable number I leave it out and report the four metrics that reproduce exactly. For context, their overall F1 is 0.882 — but that's questions against prompts with a different reference, so it's the same metric, not a head-to-head with our material number. And one more thing, to show this isn't an artifact of one favourable reference: we also scored every passage against an *independent* set of nineteen English references — university lecture notes, OER, worksheets. The set-wide mean is 0.808, plus-or-minus three thousandths — a tight band — and the single closest source for every run is still our reorganized OpenStax section at 0.840. So the number holds up across independent references; it doesn't collapse the moment you change the reference."

## 9 — Multimodal relevance — bringing the figure into the metric
"My advisor asked a sharp question: BERTScore is a text metric, so how does a generated *figure* ever enter it — input versus output? Here's our answer. We let a vision model caption each figure — that turns the image input into text — and then we BERTScore that caption against the caption of the reference *figure*, OpenStax's own diagram. So the image now flows through the exact same metric as the prose. On the visual channel we get an F1 of 0.829, plus-or-minus four thousandths across the five runs — right beside the 0.840 we get on the prose. The per-figure breakdown is reassuring: our annotated frame and summary panel line up most closely with the textbook's car-and-centrifuge figure, around 0.85, because they show the same thing — radius, velocity, acceleration toward the centre. Two honest notes: this measures relevance, not quality, and because the captions are all same-domain physics they share vocabulary, so the floor is high and the spread narrow — same property as the prose number. And I checked the captions are faithful: the model read our *actual* rendered values, like radius 0.454 metres, with no hallucination."

## SECTION — Status & roadmap
## 10 — Status and roadmap
"Where we actually are: five runs across three phenomena working end to end with the full set of deliverables — the bike, three turntable runs, the fan — plus a learning-material evaluation package for my co-author. The honest limitations: the absolute acceleration needs a known reference size in the scene, though the angular velocity and period are exact either way; and our most accurate tracker is slow compared to the fast production one, which is a genuine trade-off. The roadmap is ordered by risk, not by layer — prove the measurement first, then bring the pedagogy backend over, then the single app, then the Bahasa layer."

## 11 — Limitations & scope — what this is, and isn't, yet
"I want to put the limits on one slide, because this is a pilot and I'd rather state them than have them found. On scope: the measurement-validity number is one sensor-paired clip so far, with two more already captured, so that pilot is in progress, not a final claim. The generation set is five runs across three phenomena — the turntable filmed three times, plus the bike and the fan — so it's regime coverage, not a large sample. On evaluation, only the relevance half is run; the teacher panel and the judge are designed but not yet run. And the reference covers uniform motion, so we'll add more for the non-uniform cases. Each of those has a planned fix: extend the verification gate to check the material's *prose*, not just the figures; harden the centre self-correction and automate the prompt sweep; and run the quality half. What's solid regardless: the angular results — omega, alpha, period — are exact and scale-free, and the physics is deterministic given the trajectory."

## 12 — Next plan — evaluation metrics to try
"This is the evaluation roadmap, and it's the table my co-author suggested. BERTScore is the primary metric for now — checked — because it's the one that makes us comparable. The plan is to widen the battery: BLEU for lexical n-gram overlap, ROUGE for how much of the reference content we actually cover — that's the recall side — and BLEURT, a learned-quality metric, which gets us closer to judging quality rather than just similarity. Together they triangulate relevance, coverage and fluency, instead of leaning on one embedding score."

## 13 — Paper 2 — the learning-effect study (design)
"The second paper is the obvious next question — does this actually help anyone learn? Standard design: a pre-test, a post-test, and a delayed one for retention; the comparison is text-only versus multimodal, which is the test those modality figures were built for; and we control for the pre-test with ANCOVA and report effect sizes. The reason it's doable now is that the material already spans modalities and is grounded per scene, the tutor logs how students interact, and a bilingual Bahasa layer is planned for the local cohort."

## SECTION — System internals & deployment (defer; open if asked)
## 14 — The system at a glance (one diagram)
"Big picture: the app talks to our measurement service, which calls the tracker once and the language model, and hands back the student edition with the learning material, the teacher key, an annotated video, and the data. The thing I'd stress is it all runs on our own lab machines — no paid external API, and we don't depend on anyone else's servers — and the language model, a 35-billion-parameter one, runs locally, which we did for privacy, cost, and reproducibility."

## 15 — Under the hood — the request lifecycle
"If we follow one job through: the app posts the video and a little config to /analyze; the API checks it, makes an isolated workspace, drops the frozen physics code into it, queues the job, and hands back an id. The app just polls /status, and what it gets back is a live feed of what the agent is doing. The worker — one job at a time — runs the agent, which does the perception and then runs the frozen analysis. After that, three helpers run in parallel to make the figures, the video, and the learning material, and it all compiles to PDFs. The results go into Redis and the app pulls them from /result."

## 16 — Deployment & infrastructure — the full stack
"The stack itself is a Docker Compose. Caddy handles TLS, FastAPI is the API, Redis is both the job queue and where results live, a Celery worker runs the jobs one at a time, and a scheduler cleans up old workspaces. State is deliberately boring — each job is a self-contained folder on disk with the frozen code copied in, and the status sits in Redis. Physically it's three machines: one host runs the whole stack, and the tracker and the big model each sit on their own lab GPU."

## 17 — The agentic measurement pipeline (inside one job)
"And this is what's happening inside a single job. Steps one through five are the agent doing perception — it's actually writing and running its own Python — and the tracker gets called exactly once and cached. Step six is the frozen physics. Then three subagents run *together*, not in sequence: two of them, the video and the figures, are seeded code the agent runs and then visually double-checks; the third, the learning material, is the one real language-model job, and it's working from the measured numbers through a deterministic seed. A verification pass on the figures gates the final compile into PDFs."

## (blackout) — three black slides
"[Blank the screen here if you want the room's attention on you before the close — just advance through; nothing to say.]"

## 18 — Summary
"So, to pull it together: one video becomes reproducible physics, and that becomes multimodal, phenomenon-grounded learning material. The measurement already agrees with the gyroscope to a fraction of a percent, the material scores 0.840 on relevance against a real textbook, the evaluation is built to compare fairly against the prior method, and the learning study is ready to run. I'd love to hear your thoughts — happy to take questions."

---

# BACKUP — only if the prof asks "how does the measurement work?"

> These were the front of the deck before; they now sit after the Summary under `\appendix`. Jump to them on demand.

## B1 — The contribution, and the headline numbers
"If I had to say it in one line: a video replaces the phone gyroscope. And because it's a video, the same capture also gives us everything we need to write the learning material — so we're not capturing twice anymore. We lined it up with the prior method on purpose, so the two are comparable. A few numbers to anchor things — the video matches the gyroscope to about a third of a percent on angular velocity, we track around 94% of the frames on the bike clip, and the generated material scores 0.840 on BERTScore relevance against a real physics textbook section."

## B2 — Outline
"Quick map: the three methods, then the system itself and where things stand."

## SECTION — Three methods, one pipeline
## B3 — The whole system is three methods chained
"Three stages. The first — turning video into physics — is plain deterministic code; feed it the same video, you get the exact same numbers. The second is the only place a language model actually writes anything, and even then it's working from the measured numbers, not making them up. The third mirrors how the prior method evaluates, so we can compare directly. The colours carry through — blue is reproducible code, orange is the model, purple is the statistics."

## SECTION — Method 1: Measurement
## B4 — How the motion is measured (method, not code)
"At a high level it's four moves. We track the object in every frame — the detector takes a text description, so you just tell it what to follow. We fit the circle it's travelling on, and throw away points that clearly aren't on it. We convert pixels to metres using something of known size in the scene. And then we differentiate the angle — once you have how the angle changes, you get angular velocity, and everything else is just physics: speed is omega times radius, centripetal acceleration is omega squared times radius. One detail that matters: we smooth the angle before differentiating, and the same angular-velocity curve feeds every number after it — so nothing can disagree with itself."

## B5 — Measurement internals — the exact recipe
"The actual recipe. The circle fit is RANSAC — it keeps guessing three points, fitting the circle through them, and seeing how many other points agree within eight pixels; we also guard against the classic failure where a giant circle 'fits' because an arc looks straight. Then there's the centre rule: we trust where the user tapped, *unless* the fitted centre is clearly better — and 'clearly better' means two things at once, a tight fit and much less wobble in the radius. After that we drop outliers, fill tiny tracking gaps along the arc, get the period two ways and cross-check them, and finally fit the angle to both a straight line and a parabola to decide whether it's spinning steadily or actually speeding up or slowing down."

## B6 — Tracking → geometry, on a real clip (the fan)
"This is real output. On the left, the points we tracked and the green circle we fit, with the centre we recovered. On the right, the same orbit in metres — and look at that spiral inward: that's the doll literally swinging outward as the fan picks up speed, until it settles onto the steady circle, the dashed one. The physics is just *visible*."

## B7 — Why the numbers are trustworthy: reproducibility by design
"A design choice I want to defend. The tempting thing is to let the model compute the physics each time. But when you do that, the output format keeps drifting, invalid numbers slip through, and — my favourite example — the estimated centre swung by a *thousand* pixels on the very same video between runs. So we don't. The physics is frozen, audited code: one fixed format, identical numbers every run, model kept to perception only. That's what lets me call the measurement an instrument and not a guess."

## B8 — Measurement validation — the accuracy pilot
"The whole thesis rests on video equalling the gyroscope, so here's the test. We film the spin and record the phone's gyroscope at the same time, and use a constant-speed turntable as an absolute reference for both. We compare the summary numbers first —'is it even close?' without worrying about clocks — then the full time-series, lined up by cross-correlation so phone clock drift doesn't matter. So far: about a third of a percent on mean angular velocity, 94% coverage, period just under one-and-a-fifth seconds. The ground truth never goes near the system, so the agreement is a real external check."

## B9 — The tracking method — a wording finding (with numbers)
"This one surprised us. The detector is open-vocabulary — it's matching the *words* you give it to parts of the image — so wording is the biggest single lever on whether tracking works. Same fan clip: call it a 'cream coloured doll' and you get 6%; call it just 'toy' and one detector jumps to 100%; but the detector we run in production wants 'yellow toy' to hit 100%. That's a sixteen-fold difference from wording alone. So for the fan we tried a few words by hand on a handful of frames before committing — calibrating the language to the model; automating that micro-sweep inside the pipeline is on the roadmap, it's not built yet."

## B10 — Robustness: self-correcting geometry, and non-uniform motion
"Two problems that look like noisy data but really aren't — they're the model being wrong about the situation. First, the centre: a human tap can land off the real axis — on the fan it was 158 pixels off — and once your centre is wrong, the radius looks like it's jumping around. So the fit takes over when it's clearly better, and the wobble drops from about 39% to 10%. Second, the leftover 'noise' was actually real physics — the fan is speeding up, smoothly, fit quality basically perfect — and the same test catches the turntables slowing down. If we'd insisted on a single 'steady speed,' we'd be wrong; instead the parabola test notices and reports the acceleration."

## SECTION — Validation across cases
## B11 — Three real cases span the three motion regimes
"To show this isn't a one-off, three real objects through the exact same pipeline, no tuning per case. The bike wheel spins steadily — it's driven. The turntable is a hand-spin slowing down. The fan is powered and speeding up. Constant speed, slowing down, speeding up — and the same line-versus-parabola test sorts all three."

## B12 — Case 1: bicycle wheel — uniform
"The simple one. The agent tracked the marker — it just called it 'red object' — fit the orbit, saw the angle was already a straight line in time, so it called the motion uniform. Omega around 5, period about 1.2 seconds. The textbook case where omega-squared-r is the whole story."

## B13 — Case 2: turntable — decelerating
"A hand-spun disc, slowing from friction. The agent tracked the 'red phone', found the centre, noticed the angle curving over time — switched to a parabola, reported a negative acceleration, called it a coast-down: omega drops from 8 down to 2. It now also reports the *tangential* acceleration, the part actually slowing it — which you'd lose if you just averaged the speed."

## B14 — Case 3: ceiling fan — accelerating
"The hard one, and the most interesting. The agent tracked the 'yellow toy', spotted that the tapped axis was 158 pixels off the circle it was actually fitting and fixed it on its own, then the parabola fit showed a clean spin-up — omega from 3 to 10, fit essentially perfect. Everything fired on this single clip: the wording, the centre correction, and the speeding-up model. And because both accelerations are changing here, this is the case where the material teaches angular acceleration straight from the phenomenon."

## B15 — Reading the kinematic readout (the fan)
"Every run spits out this readout. Top-left is the angle — if it curves, it's accelerating. Top-right is angular velocity — the ramp, and its steepness is the acceleration. Bottom-left is centripetal acceleration climbing as it speeds up. Bottom-right is the orbit, points landing on the fitted circle. All the same story told four ways, so they check each other."
