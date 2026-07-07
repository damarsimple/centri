import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../config/settings.dart';
import '../models/job.dart';
import '../models/material.dart';
import '../models/measurement.dart';
import '../services/clients.dart';
import '../services/measurement_api.dart';
import '../widgets/info_views.dart';
import '../widgets/math_text.dart';
import '../widgets/stat_card.dart';
import 'tutor_screen.dart';

class ResultsScreen extends StatefulWidget {
  final String jobId;
  const ResultsScreen({super.key, required this.jobId});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  late final MeasurementApi _api;
  late final Map<String, String> _headers;
  JobResult? _result;
  String? _error;
  VideoPlayerController? _video;
  bool _teacherMode = false;
  String _materialLevel = 'basic';

  @override
  void initState() {
    super.initState();
    final s = context.read<Settings>();
    _api = s.measurement;
    _headers = {'X-API-Key': s.measurementKey};
    _load();
  }

  @override
  void dispose() {
    _video?.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final r = await _api.result(widget.jobId);
      if (!mounted) return;
      setState(() => _result = r);
      final v = r.files.annotatedVideo;
      if (v != null) {
        final c = VideoPlayerController.networkUrl(
          Uri.parse(_api.fileUrl(v)),
          httpHeaders: _headers,
        );
        await c.initialize();
        await c.setLooping(true);
        if (!mounted) {
          c.dispose();
          return;
        }
        setState(() => _video = c);
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Results')),
      body: _error != null
          ? ErrorView(message: _error!, onRetry: () {
              setState(() => _error = null);
              _load();
            })
          : _result == null
              ? const LoadingView(message: 'Fetching results…')
              : _content(context, _result!),
    );
  }

  Widget _content(BuildContext context, JobResult r) {
    final measurement = MeasurementContext.fromStats(r.stats);
    final series = r.series;
    final worksheet = r.worksheet;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _SectionTitle('Measured physics'),
        const SizedBox(height: 12),
        _statsGrid(measurement),
        const SizedBox(height: 28),

        if (_video != null) ...[
          _SectionTitle('Annotated video'),
          const SizedBox(height: 8),
          _VideoBox(controller: _video!),
          const SizedBox(height: 28),
        ],

        if (series != null && !series.isEmpty) ...[
          _SectionTitle('Motion over time'),
          const SizedBox(height: 8),
          _ChartCard(
            title: 'Angular velocity ω(t)',
            unit: 'rad/s',
            xs: series.tS,
            ys: series.omega,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 12),
          _ChartCard(
            title: 'Centripetal acceleration aᶜ(t)',
            unit: 'm/s²',
            xs: series.tS,
            ys: series.ac,
            color: Theme.of(context).colorScheme.error,
          ),
          const SizedBox(height: 12),
          _TrajectoryCard(rM: series.rM, theta: series.theta),
          const SizedBox(height: 28),
        ],

        if (r.materials != null && r.materials!.isNotEmpty) ...[
          _MaterialSection(
            materials: r.materials!,
            level: _materialLevel,
            onLevel: (l) => setState(() => _materialLevel = l),
          ),
          const SizedBox(height: 28),
        ],

        if (worksheet != null && worksheet.questions.isNotEmpty) ...[
          Row(
            children: [
              Expanded(child: _SectionTitle('Worksheet')),
              SegmentedButton<bool>(
                style: const ButtonStyle(visualDensity: VisualDensity.compact),
                segments: const [
                  ButtonSegment(value: false, label: Text('Student')),
                  ButtonSegment(value: true, label: Text('Teacher')),
                ],
                selected: {_teacherMode},
                onSelectionChanged: (s) =>
                    setState(() => _teacherMode = s.first),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (worksheet.scenario != null && worksheet.scenario!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(worksheet.scenario!,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant)),
            ),
          for (int i = 0; i < worksheet.questions.length; i++)
            _QuestionCard(
              index: i + 1,
              q: worksheet.questions[i],
              teacher: _teacherMode,
            ),
          const SizedBox(height: 28),
        ],

        FilledButton.icon(
          onPressed: measurement.hasData
              ? () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => TutorScreen(measurement: measurement),
                    ),
                  )
              : null,
          icon: const Icon(Icons.school_outlined),
          label: const Text('Start tutoring'),
        ),
        if (!measurement.hasData) ...[
          const SizedBox(height: 8),
          Text(
            'Tutoring needs angular velocity or acceleration, which this run '
            'did not produce.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
        ],
        const SizedBox(height: 24),
        const Divider(),
        const SizedBox(height: 4),
        TextButton.icon(
          onPressed: () => _openFeedback(measurement),
          icon: const Icon(Icons.flag_outlined),
          label: const Text('Something look wrong? Tell us'),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  Future<void> _openFeedback(MeasurementContext m) async {
    final settings = context.read<Settings>();
    final result = await showModalBottomSheet<_FeedbackData>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _FeedbackSheet(),
    );
    if (result == null) return;
    try {
      await _api.sendFeedback(
        type: 'result_feedback',
        jobId: widget.jobId,
        userId: settings.userId,
        role: result.role,
        payload: {
          'wrong': result.tags,
          'comment': result.comment,
          'measurement': m.toJson(),
        },
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Thanks — your feedback was recorded')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Could not send feedback: $e')));
      }
    }
  }

  Widget _statsGrid(MeasurementContext m) {
    String? fmt(double? v, String unit) =>
        v == null ? null : '${v.toStringAsFixed(3)} $unit';

    final cards = <StatCard>[
      if (m.objectLabel != null) StatCard(label: 'Object', value: m.objectLabel!),
      if (fmt(m.radiusM, 'm') != null)
        StatCard(label: 'Radius', value: fmt(m.radiusM, 'm')!),
      if (fmt(m.meanOmegaRadS, 'rad/s') != null)
        StatCard(label: 'Angular velocity', value: fmt(m.meanOmegaRadS, 'rad/s')!),
      if (fmt(m.meanAcMs2, 'm/s²') != null)
        StatCard(label: 'Centripetal accel.', value: fmt(m.meanAcMs2, 'm/s²')!),
      if (fmt(m.periodS, 's') != null)
        StatCard(label: 'Period', value: fmt(m.periodS, 's')!),
    ];

    if (cards.isEmpty) {
      return const EmptyView(message: 'No statistics were returned.');
    }
    return Wrap(spacing: 12, runSpacing: 12, children: cards);
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);
  @override
  Widget build(BuildContext context) => Text(text,
      style: Theme.of(context)
          .textTheme
          .titleMedium
          ?.copyWith(fontWeight: FontWeight.w700));
}

/// The difficulty-tiered learning material, rendered natively: a Basic/Intermediate/
/// Advanced selector, the scene-title headline, then one card per prose section.
class _MaterialSection extends StatelessWidget {
  final Map<String, MaterialLevel> materials;
  final String level;
  final ValueChanged<String> onLevel;
  const _MaterialSection(
      {required this.materials, required this.level, required this.onLevel});

  static const _order = ['basic', 'intermediate', 'advanced'];
  static const _labels = {
    'basic': 'Basic',
    'intermediate': 'Intermediate',
    'advanced': 'Advanced',
  };

  @override
  Widget build(BuildContext context) {
    final present = _order.where(materials.containsKey).toList();
    // Fall back to the first available level if the selected one isn't present.
    final sel = materials.containsKey(level) ? level : present.first;
    final m = materials[sel]!;
    final scheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(child: _SectionTitle('Learning material')),
            if (present.length > 1)
              SegmentedButton<String>(
                style: const ButtonStyle(visualDensity: VisualDensity.compact),
                segments: [
                  for (final l in present)
                    ButtonSegment(value: l, label: Text(_labels[l] ?? l)),
                ],
                selected: {sel},
                showSelectedIcon: false,
                onSelectionChanged: (s) => onLevel(s.first),
              ),
          ],
        ),
        const SizedBox(height: 10),
        if ((m.sceneTitle ?? '').isNotEmpty)
          Text(m.sceneTitle!,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w700, color: scheme.primary)),
        if ((m.bloomObjective ?? '').isNotEmpty) ...[
          const SizedBox(height: 2),
          Text('Difficulty: ${_labels[sel] ?? sel} · ${m.bloomObjective}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant, fontStyle: FontStyle.italic)),
        ],
        const SizedBox(height: 12),
        for (final entry in m.sections.entries)
          if (entry.value.trim().isNotEmpty)
            Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(entry.key,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700, color: scheme.primary)),
                    const SizedBox(height: 6),
                    Text(entry.value.trim(),
                        style: Theme.of(context).textTheme.bodyMedium),
                  ],
                ),
              ),
            ),
      ],
    );
  }
}

/// A native line chart for a value over time (replaces the baked summary panel).
class _ChartCard extends StatelessWidget {
  final String title;
  final String unit;
  final List<double> xs;
  final List<double> ys;
  final Color color;

  const _ChartCard({
    required this.title,
    required this.unit,
    required this.xs,
    required this.ys,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final n = math.min(xs.length, ys.length);
    final spots = [for (int i = 0; i < n; i++) FlSpot(xs[i], ys[i])];
    final minY = ys.isEmpty ? 0.0 : ys.reduce(math.min);
    final maxY = ys.isEmpty ? 1.0 : ys.reduce(math.max);
    final double pad =
        ((maxY - minY).abs() * 0.1).clamp(0.01, double.infinity).toDouble();

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 14, 16, 10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$title  ($unit)',
              style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 12),
          SizedBox(
            height: 170,
            child: LineChart(
              LineChartData(
                minY: minY - pad,
                maxY: maxY + pad,
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  horizontalInterval: ((maxY - minY).abs() / 3)
                      .clamp(0.01, double.infinity)
                      .toDouble(),
                  getDrawingHorizontalLine: (_) => FlLine(
                      color: scheme.outlineVariant.withValues(alpha: 0.4),
                      strokeWidth: 1),
                ),
                titlesData: FlTitlesData(
                  topTitles:
                      const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles:
                      const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 38,
                          getTitlesWidget: (v, _) => Text(
                              v.toStringAsFixed(1),
                              style: Theme.of(context).textTheme.labelSmall))),
                  bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 22,
                          interval: (xs.isEmpty ? 1.0 : xs.last / 4)
                              .clamp(0.1, 1e9)
                              .toDouble(),
                          getTitlesWidget: (v, _) => Text('${v.toStringAsFixed(1)}s',
                              style: Theme.of(context).textTheme.labelSmall))),
                ),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    isCurved: false,
                    color: color,
                    barWidth: 2,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                        show: true, color: color.withValues(alpha: 0.10)),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The reconstructed circular path, x = r·cosθ, y = r·sinθ.
class _TrajectoryCard extends StatelessWidget {
  final List<double> rM;
  final List<double> theta;
  const _TrajectoryCard({required this.rM, required this.theta});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final n = math.min(rM.length, theta.length);
    final spots = [
      for (int i = 0; i < n; i++)
        FlSpot(rM[i] * math.cos(theta[i]), rM[i] * math.sin(theta[i]))
    ];
    final ext = spots.isEmpty
        ? 1.0
        : spots
            .map((s) => math.max(s.x.abs(), s.y.abs()))
            .reduce(math.max) *
            1.15;

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 14, 16, 10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Trajectory  (m)',
              style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 12),
          SizedBox(
            height: 220,
            child: AspectRatio(
              aspectRatio: 1,
              child: LineChart(
                LineChartData(
                  minX: -ext, maxX: ext, minY: -ext, maxY: ext,
                  gridData: const FlGridData(show: false),
                  titlesData: const FlTitlesData(show: false),
                  borderData: FlBorderData(
                      show: true,
                      border: Border.all(
                          color: scheme.outlineVariant.withValues(alpha: 0.5))),
                  lineBarsData: [
                    LineChartBarData(
                      spots: spots,
                      isCurved: false,
                      color: scheme.tertiary,
                      barWidth: 2,
                      dotData: const FlDotData(show: false),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuestionCard extends StatelessWidget {
  final int index;
  final ResultQuestion q;
  final bool teacher;
  const _QuestionCard(
      {required this.index, required this.q, required this.teacher});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 12,
                backgroundColor: scheme.primaryContainer,
                child: Text('$index',
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: scheme.onPrimaryContainer,
                        fontWeight: FontWeight.w700)),
              ),
              const SizedBox(width: 10),
              if (q.bloomLevel != null) _Chip(q.bloomLevel!),
              if (q.difficulty != null) ...[
                const SizedBox(width: 6),
                _Chip(q.difficulty!),
              ],
            ],
          ),
          const SizedBox(height: 10),
          if (q.stem != null)
            MathText(q.stem!, style: Theme.of(context).textTheme.bodyMedium),
          if (q.given != null && q.given!.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              'Given: ${q.given!.entries.map((e) => '${e.key} = ${e.value}').join(', ')}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant, fontStyle: FontStyle.italic),
            ),
          ],
          if (teacher) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: scheme.tertiaryContainer.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Answer: ${q.answer ?? "—"}${q.unit != null ? " ${q.unit}" : ""}',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w700, color: scheme.onSurface),
                  ),
                  if (q.solution != null) ...[
                    const SizedBox(height: 4),
                    MathText(q.solution!,
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String text;
  const _Chip(this.text);
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(text,
          style: Theme.of(context)
              .textTheme
              .labelSmall
              ?.copyWith(color: scheme.onSurfaceVariant)),
    );
  }
}

class _VideoBox extends StatelessWidget {
  final VideoPlayerController controller;
  const _VideoBox({required this.controller});

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final ar = c.value.aspectRatio;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: AspectRatio(
        aspectRatio: (ar.isFinite && ar > 0) ? ar : 16 / 9,
        // Rebuild on every controller value change so the overlay reflects the
        // real play/pause state (not just taps).
        child: ValueListenableBuilder<VideoPlayerValue>(
          valueListenable: c,
          builder: (context, value, _) => Stack(
            alignment: Alignment.bottomCenter,
            children: [
              VideoPlayer(c),
              GestureDetector(
                onTap: () => value.isPlaying ? c.pause() : c.play(),
                child: AnimatedOpacity(
                  opacity: value.isPlaying ? 0.0 : 1.0,
                  duration: const Duration(milliseconds: 200),
                  child: Container(
                    color: Colors.black.withValues(alpha: 0.12),
                    alignment: Alignment.center,
                    child: const Icon(Icons.play_circle_fill,
                        size: 56, color: Colors.white70),
                  ),
                ),
              ),
              VideoProgressIndicator(c, allowScrubbing: true),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeedbackData {
  final String role;
  final List<String> tags;
  final String comment;
  _FeedbackData(this.role, this.tags, this.comment);
}

class _FeedbackSheet extends StatefulWidget {
  const _FeedbackSheet();

  @override
  State<_FeedbackSheet> createState() => _FeedbackSheetState();
}

class _FeedbackSheetState extends State<_FeedbackSheet> {
  static const _tagOptions = {
    'object_label': 'Wrong object',
    'rotation_center': 'Centre is off',
    'radius': 'Radius wrong',
    'angular_velocity': 'Angular velocity wrong',
    'acceleration': 'Acceleration wrong',
    'report': 'Report unclear',
    'other': 'Other',
  };

  String _role = 'student';
  final _selected = <String>{};
  final _comment = TextEditingController();

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text("What's wrong?", style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'student', label: Text('Student')),
              ButtonSegment(value: 'teacher', label: Text('Teacher')),
            ],
            selected: {_role},
            onSelectionChanged: (s) => setState(() => _role = s.first),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: _tagOptions.entries.map((e) {
              final on = _selected.contains(e.key);
              return FilterChip(
                label: Text(e.value),
                selected: on,
                onSelected: (_) => setState(() {
                  on ? _selected.remove(e.key) : _selected.add(e.key);
                }),
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _comment,
            minLines: 2,
            maxLines: 5,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(
              labelText: 'What looked wrong, and why? (optional)',
            ),
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: (_selected.isEmpty && _comment.text.trim().isEmpty)
                ? null
                : () => Navigator.pop(
                      context,
                      _FeedbackData(
                          _role, _selected.toList(), _comment.text.trim()),
                    ),
            child: const Text('Send feedback'),
          ),
        ],
      ),
    );
  }
}
