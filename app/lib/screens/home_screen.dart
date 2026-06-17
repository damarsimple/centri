import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';
import 'briefing_screen.dart';
import 'history_screen.dart';
import 'progress_screen.dart';
import 'settings_screen.dart';
import 'upload_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<Settings>();
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Centri'),
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline),
            tooltip: 'How it works',
            onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => const BriefingScreen(gate: false))),
          ),
          IconButton(
            icon: const Icon(Icons.history),
            tooltip: 'History',
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const HistoryScreen())),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Settings',
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const SettingsScreen())),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 8),
              Icon(Icons.motion_photos_on,
                  size: 72, color: scheme.primary),
              const SizedBox(height: 16),
              Text(
                'Circular Motion from Video',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                'Record an object spinning, mark it and its rotation centre, '
                'and Centri measures the physics — then tutors you through it.',
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: scheme.onSurfaceVariant),
              ),
              const SizedBox(height: 32),
              FilledButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => settings.briefingSeen
                        ? const UploadScreen()
                        : const BriefingScreen(gate: true),
                  ),
                ),
                icon: const Icon(Icons.videocam),
                label: const Text('New analysis'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const HistoryScreen())),
                icon: const Icon(Icons.history),
                label: const Text('View past analyses'),
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const ProgressScreen(
                            jobId: 'demo', demo: true))),
                icon: const Icon(Icons.auto_awesome, size: 18),
                label: const Text('Preview the live analysis view'),
              ),
              const SizedBox(height: 24),
              _StatusChip(settings: settings),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final Settings settings;
  const _StatusChip({required this.settings});

  @override
  Widget build(BuildContext context) {
    final ok = settings.measurementKey.isNotEmpty && settings.isConfigured;
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => const SettingsScreen())),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(ok ? Icons.check_circle_outline : Icons.warning_amber_rounded,
                size: 20,
                color: ok ? scheme.primary : scheme.error),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                ok
                    ? 'Connected as ${settings.userId}'
                    : 'Tap to configure backend & API key',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            const Icon(Icons.chevron_right, size: 20),
          ],
        ),
      ),
    );
  }
}
