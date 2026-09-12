import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:loanhub_call_mobile/api/loanhub_api.dart';
import 'package:loanhub_call_mobile/mobile_role_workspace.dart';
import 'package:loanhub_call_mobile/theme/loanhub_theme.dart';

void main() {
  test('role definitions keep a focused mobile workspace for core users', () {
    expect(
      MobileRoleDefinition.forRole('company_owner').title,
      'Company leadership',
    );
    expect(
      MobileRoleDefinition.forRole('collections_officer').title,
      'Collections workspace',
    );
    expect(
      MobileRoleDefinition.forRole('borrower').title,
      'Borrower workspace',
    );
    expect(
      MobileRoleDefinition.forRole('company_admin').actions
          .map((action) => action.destination),
      contains(MobileWorkspaceDestination.calls),
    );
  });

  test('unsafe backend messages are never rendered by the mobile client', () {
    final error = LoanHubApiException(
      'DataError: psycopg2 failed [parameters: UUID(123e4567-e89b-12d3-a456-426614174000)]',
      statusCode: 500,
    ).toString();

    expect(error, 'LoanHub is temporarily unavailable. Please try again shortly.');
    expect(error, isNot(contains('psycopg')));
    expect(error, isNot(contains('123e4567')));
  });

  testWidgets('role workspace stays scroll-safe on phone and tablet widths', (
    tester,
  ) async {
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    tester.view.devicePixelRatio = 1;

    for (final size in const [
      Size(320, 568),
      Size(390, 844),
      Size(720, 1024),
    ]) {
      tester.view.physicalSize = size;
      await tester.pumpWidget(
        MaterialApp(
          theme: LoanHubTheme.light(),
          home: MobileRoleWorkspace(
            key: ValueKey(size.width),
            api: LoanHubApi(),
            initialSession: const {
              'display_name': 'Theko Koetlisi',
              'role': 'company_owner',
            },
            onNavigate: (_) {},
          ),
        ),
      );
      await tester.pump();

      expect(find.text('Company leadership'), findsOneWidget);
      expect(find.text('Your mobile workspace'), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets('borrower workspace has a usable route to company offers', (
    tester,
  ) async {
    MobileWorkspaceDestination? opened;
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: LoanHubTheme.light(),
        home: MobileRoleWorkspace(
          api: LoanHubApi(),
          initialSession: const {
            'display_name': 'Mpho',
            'role': 'borrower',
          },
          onNavigate: (destination) => opened = destination,
        ),
      ),
    );
    await tester.pump();

    await tester.scrollUntilVisible(
      find.text('Loan offers'),
      200,
      scrollable: find.byType(Scrollable),
    );
    await tester.tap(find.text('Loan offers'));
    expect(opened, MobileWorkspaceDestination.explore);
    expect(tester.takeException(), isNull);
  });

  testWidgets('authorised staff can open the compact operations workspace', (
    tester,
  ) async {
    MobileWorkspaceDestination? opened;
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: LoanHubTheme.light(),
        home: MobileRoleWorkspace(
          api: LoanHubApi(),
          initialSession: const {
            'display_name': 'Lineo',
            'role': 'collections_officer',
          },
          onNavigate: (destination) => opened = destination,
        ),
      ),
    );
    await tester.pump();

    await tester.scrollUntilVisible(
      find.text('Portable operations'),
      200,
      scrollable: find.byType(Scrollable),
    );
    await tester.tap(find.text('Portable operations'));
    expect(opened, MobileWorkspaceDestination.operations);
    expect(tester.takeException(), isNull);
  });

}
