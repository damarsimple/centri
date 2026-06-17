import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'config/settings.dart';
import 'config/theme.dart';
import 'screens/consent_screen.dart';
import 'screens/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = await Settings.load();
  runApp(CentriApp(settings: settings));
}

class CentriApp extends StatelessWidget {
  final Settings settings;
  const CentriApp({super.key, required this.settings});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: settings,
      child: MaterialApp(
        title: 'Centri',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light(),
        darkTheme: AppTheme.dark(),
        themeMode: ThemeMode.system,
        home: Consumer<Settings>(
          builder: (_, s, _) =>
              s.consentAccepted ? const HomeScreen() : const ConsentScreen(),
        ),
      ),
    );
  }
}
