# Centri App (Flutter)

The Centri product UI (`com.centri.centri_app`, Material 3) — a learner records something
spinning, marks it up, and the app measures the circular-motion physics and tutors them
through it. A standalone rebuild of the learning flow from the older native app
(`G-Uphysic`, a phyphox fork); see the top-level `~/centri/README.md` and `REPORT.md`.

## Flow

consent → home (+ first-run briefing) → upload/record → **annotate** (assisted: VLM
suggests, SAM3 verifies; user marks the rotation centre) → **live progress** (agent
self-reports its stages) → **results** (native charts + worksheet) → **tutor** (4-stage
Socratic inquiry). Plus history + HITL feedback.

Results are **native and data-driven** — `fl_chart` graphs (ω/aᶜ/trajectory), measurement
cards, a student/teacher worksheet with answers + worked solutions, and LaTeX rendering.
The only baked artifact is the annotated video (no summary PNG / PDFs).

## Backends

- Measurement (`agent-backend`) via `MeasurementApi` → `http://192.168.1.13:8088`
- Pedagogy/tutor (`pedagogy-backend`) via `PedagogyApi` → `http://192.168.1.13:8090`

Defaults live in `lib/config/settings.dart`. The phone reaches these over the LAN; the
host must `ufw allow` ports 8088/8090 from `192.168.1.0/24`.

## Run / build

Flutter lives at `/opt/flutter` (the AUR wrapper is broken). Invoke it directly:

```bash
env FLUTTER_ROOT=/opt/flutter /opt/flutter/bin/flutter run -d <device>      # dev
env FLUTTER_ROOT=/opt/flutter /opt/flutter/bin/flutter build apk --debug    # APK
env FLUTTER_ROOT=/opt/flutter /opt/flutter/bin/flutter analyze              # lint
```

**Gotcha:** the `video_thumbnail` dependency needs a manual patch to
`~/.pub-cache/hosted/pub.dev/video_thumbnail-0.5.6/android/build.gradle` (strip its
`buildscript`/jcenter, set `compileSdkVersion 36`). `flutter pub get` reverts it — re-apply
or the Android build fails on `:video_thumbnail`.

## Layout

`lib/` — `config/` (settings, theme), `models/`, `services/` (`measurement_api`,
`pedagogy_api`, `progress_demo`), `screens/` (home, briefing, upload, annotate, progress,
results, tutor, history, settings), `widgets/` (`math_text`, charts, info views).
