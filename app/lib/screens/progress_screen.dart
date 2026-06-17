import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';
import '../models/job.dart';
import '../services/clients.dart';
import '../services/progress_demo.dart';
import '../widgets/info_views.dart';
import 'results_screen.dart';

class ProgressScreen extends StatefulWidget {
  final String jobId;

  /// When true, the screen is driven by a scripted local feed instead of the
  /// backend — lets you experience the live view with no server running.
  final bool demo;

  const ProgressScreen({super.key, required this.jobId, this.demo = false});

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  Timer? _timer;
  StreamSubscription<JobStatus>? _demoSub;
  JobStatus? _status;
  String? _error;
  bool _demoFinished = false;

  @override
  void initState() {
    super.initState();
    if (widget.demo) {
      _demoSub = demoProgressStream().listen((s) {
        if (!mounted) return;
        setState(() {
          _status = s;
          if (s.isDone) _demoFinished = true;
        });
      });
    } else {
      _poll();
      _timer = Timer.periodic(const Duration(seconds: 3), (_) => _poll());
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _demoSub?.cancel();
    super.dispose();
  }

  Future<void> _poll() async {
    try {
      final s = await context.read<Settings>().measurement.status(widget.jobId);
      if (!mounted) return;
      setState(() {
        _status = s;
        _error = null;
      });
      if (s.isDone) {
        _timer?.cancel();
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => ResultsScreen(jobId: widget.jobId)),
        );
      } else if (s.isFailed) {
        _timer?.cancel();
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _status;

    Widget body;
    if (s != null && s.isFailed) {
      body = ErrorView(
        message: 'Analysis failed.\n${s.message ?? ''}',
        onRetry: () => Navigator.pop(context),
      );
    } else if (s == null) {
      body = const Center(child: CircularProgressIndicator());
    } else {
      body = _Feed(
        status: s,
        error: _error,
        demoFinished: _demoFinished,
        onSeeResults: widget.demo
            ? null
            : () => Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(
                      builder: (_) => ResultsScreen(jobId: widget.jobId)),
                ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.demo ? 'Live view (demo)' : 'Analyzing'),
        automaticallyImplyLeading: widget.demo,
      ),
      body: SafeArea(child: body),
    );
  }
}

class _Feed extends StatelessWidget {
  final JobStatus status;
  final String? error;
  final bool demoFinished;
  final VoidCallback? onSeeResults;

  const _Feed({
    required this.status,
    this.error,
    this.demoFinished = false,
    this.onSeeResults,
  });

  @override
  Widget build(BuildContext context) {
    final s = status;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        _HeaderCard(status: s),
        const SizedBox(height: 14),
        if (demoFinished) ...[
          _DoneBanner(onSeeResults: onSeeResults),
          const SizedBox(height: 14),
        ] else
          _NowCard(status: s),
        const SizedBox(height: 22),
        _SectionLabel(icon: Icons.checklist_rounded, text: 'Stages'),
        const SizedBox(height: 8),
        _StageList(stages: s.stages),
        const SizedBox(height: 22),
        _SectionLabel(icon: Icons.timeline_rounded, text: 'Activity'),
        const SizedBox(height: 8),
        _ActivityList(activities: s.activities),
        if (error != null) ...[
          const SizedBox(height: 16),
          Text('Reconnecting… ($error)',
              textAlign: TextAlign.center,
              style: TextStyle(
                  color: Theme.of(context).colorScheme.error, fontSize: 12)),
        ],
      ],
    );
  }
}

class _HeaderCard extends StatelessWidget {
  final JobStatus status;
  const _HeaderCard({required this.status});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final pct = status.progressPct.clamp(0, 100);
    final done = status.isDone;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [scheme.primaryContainer, scheme.surfaceContainerHigh],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 64,
            height: 64,
            child: Stack(
              alignment: Alignment.center,
              children: [
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: pct / 100),
                  duration: const Duration(milliseconds: 600),
                  curve: Curves.easeOut,
                  builder: (_, v, _) => CircularProgressIndicator(
                    value: v == 0 && !done ? null : v,
                    strokeWidth: 6,
                    backgroundColor: scheme.onPrimaryContainer.withValues(alpha: 0.12),
                  ),
                ),
                done
                    ? Icon(Icons.check_rounded,
                        color: scheme.primary, size: 30)
                    : Text('$pct%',
                        style: Theme.of(context)
                            .textTheme
                            .labelLarge
                            ?.copyWith(fontWeight: FontWeight.w700)),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  done ? 'Done' : 'Measuring the motion',
                  style: Theme.of(context)
                      .textTheme
                      .labelMedium
                      ?.copyWith(color: scheme.onSurfaceVariant),
                ),
                const SizedBox(height: 2),
                Text(
                  status.step ?? 'Working…',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                if (status.elapsedS != null) ...[
                  const SizedBox(height: 4),
                  Text('${status.elapsedS}s elapsed',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NowCard extends StatefulWidget {
  final JobStatus status;
  const _NowCard({required this.status});

  @override
  State<_NowCard> createState() => _NowCardState();
}

class _NowCardState extends State<_NowCard> {
  bool _thinkingOpen = true;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final thinking = widget.status.thinking;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2.4),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  widget.status.currentAction ?? 'Thinking…',
                  style: Theme.of(context)
                      .textTheme
                      .titleSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          if (thinking != null && thinking.isNotEmpty) ...[
            const SizedBox(height: 12),
            InkWell(
              onTap: () => setState(() => _thinkingOpen = !_thinkingOpen),
              borderRadius: BorderRadius.circular(8),
              child: Row(
                children: [
                  Icon(Icons.psychology_alt_outlined,
                      size: 16, color: scheme.primary),
                  const SizedBox(width: 6),
                  Text('Thinking',
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          color: scheme.primary, fontWeight: FontWeight.w600)),
                  const Spacer(),
                  Icon(_thinkingOpen ? Icons.expand_less : Icons.expand_more,
                      size: 18, color: scheme.onSurfaceVariant),
                ],
              ),
            ),
            AnimatedCrossFade(
              duration: const Duration(milliseconds: 200),
              crossFadeState: _thinkingOpen
                  ? CrossFadeState.showFirst
                  : CrossFadeState.showSecond,
              firstChild: Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  thinking,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                        fontStyle: FontStyle.italic,
                        height: 1.35,
                      ),
                ),
              ),
              secondChild: const SizedBox(width: double.infinity),
            ),
          ],
        ],
      ),
    );
  }
}

class _DoneBanner extends StatelessWidget {
  final VoidCallback? onSeeResults;
  const _DoneBanner({this.onSeeResults});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: scheme.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(Icons.celebration_rounded, color: scheme.onPrimaryContainer),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Analysis complete — every stage finished.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: scheme.onPrimaryContainer,
                  fontWeight: FontWeight.w600),
            ),
          ),
          if (onSeeResults != null)
            TextButton(onPressed: onSeeResults, child: const Text('Results')),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final IconData icon;
  final String text;
  const _SectionLabel({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        Icon(icon, size: 18, color: scheme.onSurfaceVariant),
        const SizedBox(width: 8),
        Text(text,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700)),
      ],
    );
  }
}

class _StageList extends StatelessWidget {
  final List<StageItem> stages;
  const _StageList({required this.stages});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    if (stages.isEmpty) {
      return Text('Preparing…',
          style: Theme.of(context).textTheme.bodySmall);
    }
    return Column(
      children: [
        for (final st in stages)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              children: [
                _StageIcon(status: st.status),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    st.label,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: st.status == 'pending'
                              ? scheme.onSurfaceVariant
                              : scheme.onSurface,
                          fontWeight: st.isActive
                              ? FontWeight.w700
                              : FontWeight.w400,
                        ),
                  ),
                ),
                if (st.isActive)
                  Text('now',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: scheme.primary, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
      ],
    );
  }
}

class _StageIcon extends StatelessWidget {
  final String status;
  const _StageIcon({required this.status});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    switch (status) {
      case 'done':
        return Icon(Icons.check_circle_rounded,
            size: 22, color: scheme.primary);
      case 'active':
        return SizedBox(
          width: 22,
          height: 22,
          child: Padding(
            padding: const EdgeInsets.all(2),
            child: CircularProgressIndicator(
                strokeWidth: 2.6, color: scheme.primary),
          ),
        );
      default:
        return Icon(Icons.radio_button_unchecked,
            size: 22, color: scheme.outlineVariant);
    }
  }
}

class _ActivityList extends StatelessWidget {
  final List<ActivityItem> activities;
  const _ActivityList({required this.activities});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    if (activities.isEmpty) {
      return Text('No actions yet.',
          style: Theme.of(context).textTheme.bodySmall);
    }
    // Newest first.
    final items = activities.reversed.toList();
    return Column(
      children: [
        for (final a in items)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHigh,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _ActivityLeading(a: a),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(a.title,
                          style: Theme.of(context)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w600)),
                      if (a.detail != null && a.detail!.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          a.detail!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: scheme.onSurfaceVariant),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _ActivityLeading extends StatelessWidget {
  final ActivityItem a;
  const _ActivityLeading({required this.a});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    if (a.isRunning) {
      return const SizedBox(
        width: 18,
        height: 18,
        child: Padding(
          padding: EdgeInsets.all(1),
          child: CircularProgressIndicator(strokeWidth: 2.2),
        ),
      );
    }
    if (a.isError) {
      return Icon(Icons.error_outline_rounded, size: 18, color: scheme.error);
    }
    final icon = switch (a.kind) {
      'read' => Icons.menu_book_outlined,
      'write' => Icons.edit_outlined,
      'track' => Icons.my_location_outlined,
      _ => Icons.terminal_rounded,
    };
    return Icon(icon, size: 18, color: scheme.primary);
  }
}
