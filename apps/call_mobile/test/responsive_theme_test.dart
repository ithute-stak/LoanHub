import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:loanhub_call_mobile/api/loanhub_api.dart';
import 'package:loanhub_call_mobile/layout/loanhub_responsive.dart';
import 'package:loanhub_call_mobile/legal/terms_and_conditions.dart';
import 'package:loanhub_call_mobile/main.dart';
import 'package:loanhub_call_mobile/theme/loanhub_theme.dart';

void main() {
  test('LoanHub uses the established product brand colors', () {
    expect(LoanHubColors.primary, const Color(0xFF0B5EA8));
    expect(LoanHubColors.brandGreen, const Color(0xFF37A928));
    expect(LoanHubColors.brandNavy, const Color(0xFF062B55));
    expect(LoanHubColors.softBlue, const Color(0xFFEDF6FF));
  });

  test('responsive breakpoints protect narrow phones and tablets', () {
    expect(LoanHubBreakpoints.dashboardColumns(320), 1);
    expect(LoanHubBreakpoints.dashboardColumns(390), 2);
    expect(LoanHubBreakpoints.stackToolbar(360), isTrue);
    expect(LoanHubBreakpoints.useNavigationRail(719), isFalse);
    expect(LoanHubBreakpoints.useNavigationRail(720), isTrue);
  });

  testWidgets('landing page renders on a compact phone without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: LoanHubTheme.light(),
        home: LandingPage(api: LoanHubApi(), onSignedIn: () async {}),
      ),
    );
    await tester.pump();

    expect(
      find.text('Chat. Call. Move money. Access LoanHub.'),
      findsOneWidget,
    );
    expect(find.text('SIGN IN'), findsOneWidget);
    expect(find.text('I AM INTERESTED IN LOANHUB'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('terms page renders on a compact phone without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: LoanHubTheme.light(),
        home: const TermsConditionsPage(),
      ),
    );
    await tester.pump();

    expect(find.text('LoanHub Mobile Terms & Conditions'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
