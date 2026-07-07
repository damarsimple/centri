# Centri — predicted Q&A

Likely questions from the advisor, grouped by theme, with answers you can give in your own words. Bold line is the short answer; the rest is backup if he pushes.

---

## Measurement validity (the core thesis)

**Q: How do you actually know the video is right, without trusting the gyroscope?**
The gyroscope isn't the ground truth, it's the thing we're comparing against. The real ground truth is a constant-speed source, the turntable at a known RPM. Both the video and the gyroscope get checked against that absolute number, so we're not assuming either one is correct. The turntable RPM is set by the device, independent of our system.

**Q: How did you get the fan's absolute scale right?**
The angular quantities are exact and scale-free: angular velocity, angular acceleration, period. The absolute linear values (radius, speed, centripetal acceleration) need the real-world size of a reference object. For the fan I measured the blade — a single blade is about 47–50 cm long and 15 cm wide — which calibrates to roughly 0.32 m for the bounding box the tracker reports, giving an orbit radius of about 0.45 m and a mean centripetal acceleration of about 21.8 m/s² (≈ 2.2 g). An earlier provisional 1.3 m guess had produced an absurd 1.84 m radius; the measured reference fixes that. Nothing about omega or alpha changes — those never depended on scale.

**Q: The camera is 2D. If the spin plane is tilted toward the camera, a circle looks like an ellipse. Doesn't that break the circle fit?**
Yes, that's the main geometric assumption. We shoot roughly face-on, so the projection stays close to a circle, and the fit residuals confirm it: the fan came out at about 5% radius scatter once the centre was right. For a deliberately tilted plane you'd fit an ellipse and rectify it back to a circle. That's a clean extension, not a redesign, and it's on the honest-limitations list.

**Q: What about frame rate and fast spins? Could you be aliasing?**
At the speeds we measure the toy is going around once or twice a second, and at 60 fps that's 30 to 50 frames per revolution, so no aliasing. A fan blade at full speed would absolutely alias, which is exactly why we track the slow-moving toy on the blade, not the blade tip. A genuinely fast spin would need high-speed capture, and we'd flag it.

**Q: Why RANSAC instead of a plain least-squares circle fit?**
Tracking occasionally drops a frame or lands a point off the object during motion blur. Least squares lets one bad point drag the whole fit. RANSAC finds the circle the majority of points agree on and treats the rest as outliers, which is what we want on real, slightly noisy tracks.

**Q: Your centre-override could overrule a correct human tap. How is that safe?**
It only fires when two independent conditions both hold: the fit is tight in absolute terms, and it cuts the radius scatter by a large margin versus the mark. A correct human tap already produces low scatter, so the second condition fails and we keep the tap. A degenerate fit produces high scatter, so it fails too. We also logged every case across ten clips: only the fan triggered it, and there the mark was genuinely 158 px off.

---

## Tracking

**Q: The tracker is non-deterministic. Doesn't that contradict "same video, same numbers"?**
Two separate stages. Tracking is the non-deterministic part, so we run it once, gate it on a coverage threshold with a few bounded retries, and then cache the trajectory. Everything after that, the physics, is fully deterministic given that cached trajectory. So the reproducibility claim is precise: identical trajectory in, byte-identical stats out.

**Q: Wording changes coverage by 16x. Isn't that too fragile for real users?**
It's a real sensitivity. Today we handle it manually: for a new object we try a few candidate words on a handful of frames and keep the one that tracks best before committing. Automating that micro-sweep so the user just names the object once is on the roadmap — I want to be clear it's not built yet, it's a manual step now.

**Q: How well does the detector generalise across objects and lighting?**
It's open-vocabulary, so it handles arbitrary objects from a text description, which is the whole reason we can do bikes, turntables, and fans with no per-object training. The failure mode is wording, which we handle, plus very small or heavily blurred targets, which is an honest limit.

---

## Generation and the language model

**Q: How do you know the generated learning material is actually correct?**
The numbers in the material come from the deterministic physics, not the model, through a fixed seed — the variables, the formula relations, and a time-anchored omega-of-t — so the quantities are right by construction. The model only writes the prose around them, and the prompt forbids introducing any number not in the seed. The figure outputs are verified before compile. The remaining risk is wording, which the teacher panel and the judge are there to catch.

**Q: Why a local 35B model and not GPT-4?**
Three reasons: privacy of student data, cost at classroom scale, and reproducibility, since we control the weights. The model only writes grounded prose over fixed numbers, which is well within a 35B model's range. We're not asking it to do the physics.

**Q: Could it hallucinate a wrong formula or answer?**
It can phrase things poorly, but the answer key is generated alongside and the quantities are fixed, so a wrong number is detectable against the measured values. That's a deliberate design choice: keep the model away from anything we can compute.

---

## Evaluation

**Q: BERTScore measures similarity to a reference, not quality. Why report it?**
Exactly, and we say so on the slide. We keep it only because the paper we're comparing to uses it, so it's an apples-to-apples number. Quality will be judged separately by the teacher panel and the LLM judge — and I should be upfront that that quality half is designed but **not yet run**, so right now we report relevance only. BERTScore alone is not our quality claim.

**Q: What's your reference, and isn't 0.840 just self-comparison?**
No — the reference is independent of our pipeline. It's a real, published textbook section, OpenStax College Physics 6.2 on centripetal acceleration. Our material never saw it. So 0.840 is genuine relevance against authoritative external content. One honest caveat: §6.2 is *uniform* circular motion, so it doesn't cover our spin-up/slow-down cases — we'll add further references for the non-uniform content. If my co-author prefers a different or additional reference, we swap it in and the method stays identical.

**Q: But you don't diff the raw PDF — you compare against a reorganized excerpt. Isn't that rigged?**
Fair to ask, and it's on the slide. Three things make it honest. First, the reference text is the *authentic* OpenStax §6.2 — reorganized into our five sections, not rewritten or paraphrased — so candidate and reference align section by section, which is what makes a per-section score meaningful at all. Second, the reorganization was done *independently* of our generation: the tell is that the textbook's "over time" section is its own car-and-centrifuge worked examples, nothing to do with our fan numbers, so nothing leaks in to inflate the score. Third, we report whole-passage F1 too, not just the favourable sections, so it isn't selective. The sections that score *lower* — scenario, reading the figures — are exactly the grounded parts a generic textbook can't supply, which is our value-add. And the strongest answer: we re-scored every passage against an *independent* set of 19 English references (university lecture notes, OER, worksheets) — set-wide mean 0.808 ± 0.003, a tight band, with the reorganized §6.2 still the closest single source. The number doesn't depend on the one reference we curated; it holds across independent sources we didn't touch.

**Q: The prior method's Table 3 has five metrics. Do you report all of them?**
We reproduce four of the five automatic metrics — BERT Precision, Recall, F1, and a diversity score. Whole-passage results are P 0.837, R 0.842, F1 0.840 (±0.002), and diversity 0.204. The fifth, the LSTM language-fluency score, uses the prior method's own trained LSTM model, which we don't have — so we omit it rather than substitute a different, non-comparable proxy. (Their overall F1 is 0.882, but that's question-vs-prompt against a different reference, so it isn't a head-to-head number with our material-vs-textbook 0.840.)

**Q: Why only BERTScore? Are you adding other metrics?**
BERTScore is the primary metric for now because it's the comparability anchor. The roadmap (on the "next plan" slide) is to widen the battery: BLEU for lexical n-gram precision, ROUGE-1/2/L for content recall — how much of the reference we actually cover — and BLEURT, a learned-quality metric that judges candidate quality rather than raw similarity. They triangulate relevance, coverage and fluency; BLEU/ROUGE will read lower on paraphrased material by nature, which is exactly why they're complementary diagnostics, not the headline.

**Q: Five objects is small. What about statistical power?**
Fair, and I'd frame it honestly: it's five runs across three distinct phenomena — the turntable filmed three times, plus the bike and the fan — so it's regime coverage (uniform / decelerating / accelerating), not five independent objects. For the automatic metric that's enough to show the pipeline produces consistent, on-topic material — plus-or-minus two thousandths on F1. The real inferential statistics come in the learning study, powered separately with the teacher panel and the student cohort. This is a development set, not the hypothesis test.

**Q: The LLM judge and the generator are similar models. Isn't that biased?**
It's a fair concern, which is why the judge is a cross-check, not the verdict. The human panel is the authority on quality. We can also use a different model family for the judge to reduce shared bias, and report agreement between the judge and the teachers via Pearson r.

---

## Pedagogy and the learning study

**Q: Why centripetal motion specifically? Does this generalise?**
We chose it to line up with the paper we're comparing against. The pipeline isn't specific to it though: anything with a measurable trajectory and a known relationship could be generated the same way. Circular motion is the first instance, not the ceiling.

**Q: In the multimodal study, how do you avoid confounds between modality and content?**
The material presents the same measured physics across modalities — image, graph, table, text — so we can hold the content fixed and vary only the presentation. We also control for the pre-test with ANCOVA and measure cognitive load with a standard scale, so modality effects don't get confused with prior ability or sheer load.

**Q: How does the tutor know a student's ability?**
That's the pedagogy backend we're porting next: an ability estimate updated from responses, plus misconception tracking from the interaction logs. The measurement side feeds it the content; the ability model is the next phase.

---

## Alignment with the prior method, and contribution

**Q: Is it a fair comparison if you use video and they use a sensor?**
The modality is exactly the contribution, so we keep everything else identical: same topic, same difficulty structure, same evaluation battery. The comparison isn't "is video better at being a sensor," it's "does swapping the sensor for video preserve or improve the educational output," measured the same way.

**Q: Where does your work end and your co-author's begin?**
She owns the evaluation references and the prior (sensor-based) method side. I own the video measurement pipeline and the generation built on it. The joint paper is the comparison, which is why the evaluation is deliberately shared.

---

## System, scale, privacy

**Q: One job at a time. Does that scale to a class of thirty?**
The constraint is the single GPU, not the design. Jobs queue and run sequentially now because we have one box. Adding workers or GPUs scales it horizontally without changing anything else, since each job is already isolated.

**Q: How long does one video take?**
A few minutes end to end with the production tracker, dominated by tracking and the language-model steps. The accurate-but-slow tracker pushes that to around ten minutes, which is the trade-off on the slide.

**Q: Student videos are sensitive. How do you handle privacy?**
Everything runs on our own lab machines, including the language model, with no external API. Nothing leaves the lab network, which is one of the reasons we run the model locally.

---

## The "what's your weakness" question

**Q: What's the biggest limitation right now?**
It's a pilot, and I'd rather state the limits than have them found — they're on the limitations slide. The two I'd lead with: (1) the *quality* evaluation isn't run yet — so far we have relevance (BERTScore), not the teacher/judge verdict; and (2) measurement validity rests on one sensor-paired clip so far, with two more captured, so that's in progress, not a final claim. Smaller ones: absolute distances depend on a known reference size (angular results don't), the circle fit assumes a roughly face-on view, and the reference covers only uniform motion so far. Every one of these has a planned fix, and the angular kinematics are exact regardless.
