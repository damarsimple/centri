import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';

/// Shown once, before first use. Explains what the pilot records and lets the
/// learner opt out of anonymous usage data while still using the app.
class ConsentScreen extends StatefulWidget {
  const ConsentScreen({super.key});

  @override
  State<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends State<ConsentScreen> {
  bool _shareData = true;

  Future<void> _accept() async {
    await context.read<Settings>().acceptConsent(telemetry: _shareData);
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(24),
                children: [
                  const SizedBox(height: 8),
                  Icon(Icons.privacy_tip_outlined, size: 56, color: scheme.primary),
                  const SizedBox(height: 16),
                  Text('Before we start', style: text.headlineSmall),
                  const SizedBox(height: 16),
                  Text(
                    'Centri is part of a research study on learning circular '
                    'motion from video. To improve it, we record:',
                    style: text.bodyMedium,
                  ),
                  const SizedBox(height: 16),
                  _point(context, Icons.tune,
                      'How you set up a measurement — including where our '
                      'suggestions were right or you corrected them.'),
                  _point(context, Icons.flag_outlined,
                      'Feedback you choose to send about a result.'),
                  _point(context, Icons.videocam_outlined,
                      'The videos you submit and the measurements produced.'),
                  const SizedBox(height: 16),
                  Text(
                    'We do not collect personal information beyond the student '
                    'ID you set. You can change your choice anytime in Settings.',
                    style: text.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
                  ),
                  const SizedBox(height: 16),
                  Card(
                    margin: EdgeInsets.zero,
                    child: SwitchListTile(
                      value: _shareData,
                      onChanged: (v) => setState(() => _shareData = v),
                      title: const Text('Share anonymous usage data'),
                      subtitle: const Text(
                          'Helps us see where the app guesses wrong. '
                          'You can still use everything if this is off.'),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              child: FilledButton(
                onPressed: _accept,
                child: const Text('I understand — continue'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _point(BuildContext context, IconData icon, String body) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: scheme.primary),
          const SizedBox(width: 12),
          Expanded(child: Text(body, style: Theme.of(context).textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
