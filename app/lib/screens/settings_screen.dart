import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/settings.dart';
import '../widgets/async_button.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _measUrl;
  late final TextEditingController _measKey;
  late final TextEditingController _pedaUrl;
  late final TextEditingController _userId;
  late bool _telemetry;

  @override
  void initState() {
    super.initState();
    final s = context.read<Settings>();
    _measUrl = TextEditingController(text: s.measurementUrl);
    _measKey = TextEditingController(text: s.measurementKey);
    _pedaUrl = TextEditingController(text: s.pedagogyUrl);
    _userId = TextEditingController(text: s.userId);
    _telemetry = s.telemetryEnabled;
  }

  @override
  void dispose() {
    _measUrl.dispose();
    _measKey.dispose();
    _pedaUrl.dispose();
    _userId.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    await context.read<Settings>().update(
          measurementUrl: _measUrl.text.trim(),
          measurementKey: _measKey.text.trim(),
          pedagogyUrl: _pedaUrl.text.trim(),
          userId: _userId.text.trim(),
          telemetryEnabled: _telemetry,
        );
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Settings saved')));
    Navigator.pop(context);
  }

  String? _url(String? v) {
    if (v == null || v.trim().isEmpty) return 'Required';
    final u = Uri.tryParse(v.trim());
    if (u == null || !u.hasScheme || !u.hasAuthority) return 'Enter a valid URL';
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            _section(context, 'Measurement backend',
                'agent-backend: turns your video into physics.'),
            TextFormField(
              controller: _measUrl,
              decoration: const InputDecoration(
                  labelText: 'Base URL', hintText: 'http://host:8082'),
              keyboardType: TextInputType.url,
              autocorrect: false,
              validator: _url,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _measKey,
              decoration: const InputDecoration(
                  labelText: 'API key (X-API-Key)'),
              autocorrect: false,
              obscureText: true,
            ),
            const SizedBox(height: 28),
            _section(context, 'Pedagogy backend',
                'The inquiry tutor & question generator.'),
            TextFormField(
              controller: _pedaUrl,
              decoration: const InputDecoration(
                  labelText: 'Base URL', hintText: 'http://host:8090'),
              keyboardType: TextInputType.url,
              autocorrect: false,
              validator: _url,
            ),
            const SizedBox(height: 28),
            _section(context, 'Learner', 'Identifies you to the tutor.'),
            TextFormField(
              controller: _userId,
              decoration: const InputDecoration(labelText: 'Student ID'),
              autocorrect: false,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: 28),
            _section(context, 'Privacy', 'Part of the research pilot.'),
            Card(
              margin: EdgeInsets.zero,
              child: SwitchListTile(
                value: _telemetry,
                onChanged: (v) => setState(() => _telemetry = v),
                title: const Text('Share anonymous usage data'),
                subtitle: const Text(
                    'Records where the app\'s setup guesses were right or '
                    'corrected, to improve it. Result feedback you send is '
                    'unaffected.'),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12),
              ),
            ),
            const SizedBox(height: 32),
            AsyncButton(
              icon: Icons.save_outlined,
              onPressed: _save,
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section(BuildContext context, String title, String subtitle) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 2),
          Text(subtitle,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}
