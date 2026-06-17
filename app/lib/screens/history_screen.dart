import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';
import '../models/job.dart';
import '../services/clients.dart';
import '../services/measurement_api.dart';
import '../widgets/info_views.dart';
import 'progress_screen.dart';
import 'results_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late final MeasurementApi _api;
  List<JobEntry>? _jobs;
  String? _error;

  @override
  void initState() {
    super.initState();
    _api = context.read<Settings>().measurement;
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final jobs = await _api.jobs();
      if (mounted) setState(() => _jobs = jobs);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  Future<void> _delete(JobEntry job) async {
    try {
      await _api.deleteJob(job.jobId);
      setState(() => _jobs?.removeWhere((j) => j.jobId == job.jobId));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Delete failed: $e')));
      }
    }
  }

  IconData _statusIcon(String? status) {
    switch (status?.toLowerCase()) {
      case 'done':
        return Icons.check_circle;
      case 'failed':
      case 'error':
        return Icons.error;
      default:
        return Icons.hourglass_top;
    }
  }

  /// Human-friendly elapsed time: "45s", "2m 54s", "1h 03m".
  static String _fmtElapsed(int s) {
    if (s < 0) s = 0;
    final h = s ~/ 3600;
    final m = (s % 3600) ~/ 60;
    final sec = s % 60;
    if (h > 0) return '${h}h ${m.toString().padLeft(2, '0')}m';
    if (m > 0) return sec == 0 ? '${m}m' : '${m}m ${sec}s';
    return '${sec}s';
  }

  /// Relative submission time: "just now", "5 min ago", "3 h ago", "2 d ago".
  static String _fmtAgo(DateTime when) {
    final d = DateTime.now().difference(when);
    if (d.inSeconds < 45) return 'just now';
    if (d.inMinutes < 60) return '${d.inMinutes} min ago';
    if (d.inHours < 24) return '${d.inHours} h ago';
    if (d.inDays < 7) return '${d.inDays} d ago';
    return '${when.year}-${when.month.toString().padLeft(2, '0')}-${when.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    Widget body;
    if (_error != null) {
      body = ErrorView(message: _error!, onRetry: _load);
    } else if (_jobs == null) {
      body = const LoadingView(message: 'Loading history…');
    } else if (_jobs!.isEmpty) {
      body = const EmptyView(
          icon: Icons.movie_filter_outlined,
          message: 'No analyses yet.\nRun one from the home screen.');
    } else {
      body = RefreshIndicator(
        onRefresh: _load,
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: _jobs!.length,
          separatorBuilder: (_, _) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final job = _jobs![i];
            final status = job.status?.toLowerCase();
            final done = status == 'done';
            final failed = status == 'failed' || status == 'error';
            final running = !done && !failed;

            // Title: the recorded object (what the student measured). Falls back to
            // a friendly status when no label was captured. The short id is kept in
            // the subtitle for support/debugging.
            final shortId =
                job.jobId.length >= 8 ? job.jobId.substring(0, 8) : job.jobId;
            final hasName =
                job.objectName != null && job.objectName!.trim().isNotEmpty;
            final title = hasName
                ? job.objectName!.trim()
                : done
                    ? 'Completed'
                    : failed
                        ? 'Couldn’t finish'
                        : (job.step != null && job.step!.isNotEmpty
                            ? job.step!
                            : 'Analysing…');
            // Status line: outcome/step (only when the title isn't already it),
            // relative submission time, run duration, and live % for running jobs.
            final statusWord = done
                ? 'Completed'
                : failed
                    ? 'Couldn’t finish'
                    : running && job.step != null && job.step!.isNotEmpty
                        ? job.step!
                        : 'Analysing…';
            final subtitle = [
              if (hasName) statusWord,
              if (job.createdAt != null) _fmtAgo(job.createdAt!),
              if (job.elapsedS != null) _fmtElapsed(job.elapsedS!),
              if (running && job.progressPct > 0) '${job.progressPct}%',
              '#$shortId',
            ].join(' · ');
            // done → results; running/failed → progress screen (it renders the
            // live feed for running jobs and the error view for failed ones).
            void open() => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => done
                        ? ResultsScreen(jobId: job.jobId)
                        : ProgressScreen(jobId: job.jobId),
                  ),
                );
            return Dismissible(
              key: ValueKey(job.jobId),
              direction: DismissDirection.endToStart,
              background: Container(
                color: scheme.errorContainer,
                alignment: Alignment.centerRight,
                padding: const EdgeInsets.only(right: 20),
                child: Icon(Icons.delete_outline, color: scheme.onErrorContainer),
              ),
              onDismissed: (_) => _delete(job),
              child: ListTile(
                leading: Icon(_statusIcon(job.status),
                    color: done
                        ? scheme.primary
                        : failed
                            ? scheme.error
                            : scheme.onSurfaceVariant),
                title: Text(title,
                    maxLines: 1, overflow: TextOverflow.ellipsis),
                isThreeLine: running,
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(subtitle,
                        maxLines: 1, overflow: TextOverflow.ellipsis),
                    if (running) ...[
                      const SizedBox(height: 6),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: job.progressPct > 0
                              ? job.progressPct / 100
                              : null,
                          minHeight: 4,
                        ),
                      ),
                    ],
                  ],
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: open,
              ),
            );
          },
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: SafeArea(child: body),
    );
  }
}
