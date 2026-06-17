// Basic smoke test: the app boots to the home screen.

import 'package:flutter_test/flutter_test.dart';

import 'package:centri_app/config/settings.dart';
import 'package:centri_app/main.dart';

void main() {
  testWidgets('First launch shows consent', (WidgetTester tester) async {
    await tester.pumpWidget(CentriApp(settings: Settings()));
    await tester.pump();

    expect(find.text('Before we start'), findsOneWidget);
    expect(find.text('I understand — continue'), findsOneWidget);
  });

  testWidgets('Home screen renders once consent given',
      (WidgetTester tester) async {
    await tester.pumpWidget(CentriApp(settings: Settings(consentAccepted: true)));
    await tester.pump();

    expect(find.text('New analysis'), findsOneWidget);
  });
}
