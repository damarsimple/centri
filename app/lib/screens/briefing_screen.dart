import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';
import 'upload_screen.dart';

/// A phyphox-style "read before you do" briefing for the circular-motion
/// experiment. Shown on first use (gated before an analysis); also reachable
/// any time from the home ⓘ button as a plain info screen.
class BriefingScreen extends StatefulWidget {
  /// When true, the screen gates the analysis flow: a "Start" button leads to
  /// upload and a "don't show again" choice is offered. When false, it's a
  /// plain info screen with a Close button.
  final bool gate;

  const BriefingScreen({super.key, this.gate = true});

  @override
  State<BriefingScreen> createState() => _BriefingScreenState();
}

class _BriefingScreenState extends State<BriefingScreen> {
  bool _dontShowAgain = true;

  Future<void> _start() async {
    await context.read<Settings>().setBriefingSeen(_dontShowAgain);
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const UploadScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Before you start'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          children: [
            Text('Circular Motion from Video',
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(
              'Film something spinning. Centri tracks it frame by frame and '
              'measures the real physics of its motion.',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: scheme.onSurfaceVariant),
            ),
            const SizedBox(height: 24),

            _Section(
              icon: Icons.speed_rounded,
              title: 'What you\'ll measure',
              child: Wrap(
                spacing: 10,
                runSpacing: 10,
                children: const [
                  _Metric(symbol: 'ω', name: 'Angular velocity', unit: 'rad/s'),
                  _Metric(symbol: 'aᶜ', name: 'Centripetal accel.', unit: 'm/s²'),
                  _Metric(symbol: 'r', name: 'Radius', unit: 'm'),
                  _Metric(symbol: 'T', name: 'Period', unit: 's'),
                ],
              ),
            ),

            _Section(
              icon: Icons.functions_rounded,
              title: 'The physics',
              child: Column(
                children: [
                  const _DiagramCard(),
                  const SizedBox(height: 12),
                  Row(
                    children: const [
                      Expanded(child: _Formula('ω = Δθ / Δt')),
                      SizedBox(width: 10),
                      Expanded(child: _Formula('v = ω r')),
                    ],
                  ),
                  const SizedBox(height: 10),
                  const _Formula('aᶜ = ω² r = v² / r', wide: true),
                ],
              ),
            ),

            _Section(
              icon: Icons.videocam_rounded,
              title: 'How to record',
              child: Column(
                children: const [
                  _Tip(Icons.center_focus_strong,
                      'Keep the camera steady — a tripod or a propped-up phone.'),
                  _Tip(Icons.straighten,
                      'Make sure the whole spinning platform is in frame so Centri can set the scale.'),
                  _Tip(Icons.refresh,
                      'Capture at least one full rotation, with the object always visible.'),
                  _Tip(Icons.wb_sunny_outlined,
                      'Bright, even lighting — dim light blurs a fast spin and the app can lose the object.'),
                  _Tip(Icons.speed,
                      'Don’t spin too fast — a steady, moderate spin tracks far better than a quick blur.'),
                ],
              ),
            ),

            _Section(
              icon: Icons.workspace_premium_outlined,
              title: 'What you\'ll get',
              child: Column(
                children: const [
                  _Output(Icons.movie_outlined, 'Annotated video',
                      'Your clip with the path, velocity and acceleration drawn on.'),
                  _Output(Icons.show_chart, 'Plots',
                      'ω(t) and aᶜ(t) over the whole clip.'),
                  _Output(Icons.school_outlined, 'Student edition PDF',
                      'A worksheet that walks you through the result.'),
                  _Output(Icons.key_outlined, 'Teacher key PDF',
                      'The same, with full solutions.'),
                ],
              ),
            ),

            _Section(
              icon: Icons.lightbulb_outline_rounded,
              title: 'What "good" looks like',
              child: const _ExampleCard(),
            ),

            const SizedBox(height: 8),
            if (widget.gate) ...[
              CheckboxListTile(
                value: _dontShowAgain,
                onChanged: (v) => setState(() => _dontShowAgain = v ?? true),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: const Text('Don\'t show this again'),
              ),
              const SizedBox(height: 4),
              FilledButton.icon(
                onPressed: _start,
                icon: const Icon(Icons.arrow_forward),
                label: const Text('Start analysis'),
              ),
            ] else
              FilledButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Got it'),
              ),
          ],
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final IconData icon;
  final String title;
  final Widget child;
  const _Section(
      {required this.icon, required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 20, color: scheme.primary),
              const SizedBox(width: 8),
              Text(title,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String symbol;
  final String name;
  final String unit;
  const _Metric({required this.symbol, required this.name, required this.unit});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: 150,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Text(symbol,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: scheme.primary, fontWeight: FontWeight.w700)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    style: Theme.of(context).textTheme.bodySmall,
                    maxLines: 2),
                Text(unit,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Formula extends StatelessWidget {
  final String text;
  final bool wide;
  const _Formula(this.text, {this.wide = false});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: wide ? double.infinity : null,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      alignment: Alignment.center,
      child: Text(text,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontFeatures: const [],
                fontStyle: FontStyle.italic,
                fontWeight: FontWeight.w600,
              )),
    );
  }
}

class _DiagramCard extends StatelessWidget {
  const _DiagramCard();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      height: 170,
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(16),
      ),
      child: CustomPaint(
        painter: _CircularMotionPainter(
          ring: scheme.outlineVariant,
          radiusLine: scheme.onSurfaceVariant,
          object: scheme.primary,
          velocity: scheme.tertiary,
          accel: scheme.error,
          labelColor: scheme.onSurface,
        ),
        child: const SizedBox.expand(),
      ),
    );
  }
}

class _CircularMotionPainter extends CustomPainter {
  final Color ring, radiusLine, object, velocity, accel, labelColor;
  _CircularMotionPainter({
    required this.ring,
    required this.radiusLine,
    required this.object,
    required this.velocity,
    required this.accel,
    required this.labelColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = math.min(size.width, size.height) * 0.32;

    // Orbit ring.
    canvas.drawCircle(
        c,
        r,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..color = ring);

    // Object position at ~ -45°.
    final theta = -math.pi / 4;
    final p = Offset(c.dx + r * math.cos(theta), c.dy + r * math.sin(theta));

    // Radius line + label.
    canvas.drawLine(
        c,
        p,
        Paint()
          ..strokeWidth = 1.5
          ..color = radiusLine);
    _label(canvas, 'r', Offset((c.dx + p.dx) / 2, (c.dy + p.dy) / 2 - 12),
        radiusLine);

    // Velocity arrow (tangent, counter-clockwise).
    final tang = Offset(-math.sin(theta), math.cos(theta));
    _arrow(canvas, p, p + tang * 46, velocity, 'v');

    // Acceleration arrow (toward centre).
    final inward = (c - p);
    final inwardN = inward / inward.distance;
    _arrow(canvas, p, p + inwardN * 46, accel, 'aᶜ');

    // Centre dot + object dot.
    canvas.drawCircle(c, 3, Paint()..color = radiusLine);
    canvas.drawCircle(p, 7, Paint()..color = object);
  }

  void _arrow(Canvas canvas, Offset from, Offset to, Color color, String tag) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(from, to, paint);
    final dir = (to - from);
    final n = dir / dir.distance;
    final left = Offset(-n.dy, n.dx);
    final tip1 = to - n * 9 + left * 5;
    final tip2 = to - n * 9 - left * 5;
    canvas.drawLine(to, tip1, paint);
    canvas.drawLine(to, tip2, paint);
    _label(canvas, tag, to + n * 10 + const Offset(-4, -6), color);
  }

  void _label(Canvas canvas, String text, Offset at, Color color) {
    final tp = TextPainter(
      text: TextSpan(
          text: text,
          style: TextStyle(
              color: color, fontSize: 13, fontWeight: FontWeight.w700)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, at);
  }

  @override
  bool shouldRepaint(covariant _CircularMotionPainter old) => false;
}

class _Tip extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Tip(this.icon, this.text);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: scheme.primary),
          const SizedBox(width: 12),
          Expanded(
              child: Text(text,
                  style: Theme.of(context).textTheme.bodyMedium)),
        ],
      ),
    );
  }
}

class _Output extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  const _Output(this.icon, this.title, this.subtitle);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: scheme.secondaryContainer,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 18, color: scheme.onSecondaryContainer),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w600)),
                Text(subtitle,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ExampleCard extends StatelessWidget {
  const _ExampleCard();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [scheme.tertiaryContainer, scheme.surfaceContainerHigh],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('A spinning turntable, 7s clip',
              style: Theme.of(context)
                  .textTheme
                  .labelMedium
                  ?.copyWith(color: scheme.onSurfaceVariant)),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              _Stat('ω', '6.4', 'rad/s'),
              _Stat('rpm', '61', ''),
              _Stat('aᶜ', '9.8', 'm/s²'),
              _Stat('r', '0.24', 'm'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  const _Stat(this.label, this.value, this.unit);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        Text(label,
            style: Theme.of(context)
                .textTheme
                .labelSmall
                ?.copyWith(color: scheme.onSurfaceVariant)),
        const SizedBox(height: 2),
        Text(value,
            style: Theme.of(context)
                .textTheme
                .titleLarge
                ?.copyWith(fontWeight: FontWeight.w700, color: scheme.primary)),
        Text(unit, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}
