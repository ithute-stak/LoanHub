import 'dart:io';

import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart';
import 'package:workmanager/workmanager.dart';

import 'api/loanhub_api.dart';
import 'api/mobile_onboarding_api.dart';
import 'business_calls.dart';
import 'layout/loanhub_responsive.dart';
import 'legal/terms_and_conditions.dart';
import 'realtime/push_service.dart';
import 'realtime/realtime_scope.dart';
import 'super_app_home.dart';
import 'theme/loanhub_theme.dart';
import 'widgets/loanhub_brand.dart';

const _syncTaskName = 'loanhub_call_sync';
const _syncTaskUniqueName = 'loanhub-call-background-sync';

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    if (task != _syncTaskName) return true;
    try {
      final api = LoanHubApi();
      await api.syncPendingCalls();
      if (await api.hasSession()) {
        // Low-frequency recovery only. Foreground updates come through the
        // shared socket and background alerts through push; this catch-up
        // closes gaps after long offline periods or OEM battery restrictions.
        await Future.wait<dynamic>([
          api.chatUnreadCount(),
          api.moneyTransfers(),
        ]);
      }
      return true;
    } catch (_) {
      return false;
    }
  });
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await LiveKitClient.initialize();
  await initialiseLoanHubFirebase();
  if (Platform.isAndroid) {
    await Workmanager().initialize(callbackDispatcher);
    await Workmanager().registerPeriodicTask(
      _syncTaskUniqueName,
      _syncTaskName,
      frequency: const Duration(minutes: 15),
      existingWorkPolicy: ExistingPeriodicWorkPolicy.update,
    );
  }
  runApp(const LoanHubApp());
}

class LoanHubApp extends StatefulWidget {
  const LoanHubApp({super.key});

  @override
  State<LoanHubApp> createState() => _LoanHubAppState();
}

class _LoanHubAppState extends State<LoanHubApp> {
  final api = LoanHubApi();
  bool? signedIn;

  @override
  void initState() {
    super.initState();
    _resolveSession();
  }

  Future<void> _resolveSession() async {
    final value = await api.hasSession();
    if (mounted) setState(() => signedIn = value);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'LoanHub',
      debugShowCheckedModeBanner: false,
      theme: LoanHubTheme.light(),
      darkTheme: LoanHubTheme.dark(),
      themeMode: ThemeMode.system,
      // The scope must wrap MaterialApp's navigator, not only the home page:
      // pushed routes such as ChatThreadPage need the same shared BLoCs.
      builder: (context, child) {
        final navigator = child ?? const SizedBox.shrink();
        return signedIn == true
            ? LoanHubRealtimeScope(api: api, child: navigator)
            : navigator;
      },
      home: signedIn == null
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : signedIn!
          ? SuperAppHome(
              api: api,
              onSignedOut: _resolveSession,
              businessCallsBuilder: (_) => BusinessCallsWorkspace(api: api),
            )
          : LandingPage(api: api, onSignedIn: _resolveSession),
    );
  }
}

class LandingPage extends StatelessWidget {
  const LandingPage({required this.api, required this.onSignedIn, super.key});

  final LoanHubApi api;
  final Future<void> Function() onSignedIn;

  @override
  Widget build(BuildContext context) {
    final padding = LoanHubBreakpoints.pagePadding(
      MediaQuery.sizeOf(context).width,
    );
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [LoanHubColors.brandNavy, LoanHubColors.primary],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: EdgeInsets.all(padding),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: LoanHubAppIcon(size: 102, radius: 30)),
                    const SizedBox(height: 16),
                    const LoanHubHorizontalLogo(
                      height: 54,
                      backgroundColor: Colors.white,
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Chat. Call. Move money. Access LoanHub.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 21,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 9),
                    const Text(
                      'One secure app for clients, interested customers, LoanHub businesses and the LoanHub platform team.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xFFDCEAF5),
                        fontSize: 15,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 26),
                    const _LandingFeature(
                      icon: Icons.chat_bubble_outline,
                      title: 'LoanHub Chats',
                      subtitle:
                          'Private and group conversations, files, voice-note support and business communication.',
                    ),
                    const SizedBox(height: 10),
                    const _LandingFeature(
                      icon: Icons.call_outlined,
                      title: 'Business Calls',
                      subtitle:
                          'Controlled client calls, transfers and company recording policies for authorised staff.',
                    ),
                    const SizedBox(height: 10),
                    const _LandingFeature(
                      icon: Icons.account_balance_wallet_outlined,
                      title: 'LoanHub Money',
                      subtitle:
                          'Traceable C2C, C2B, B2C and B2B transfer workflows backed by approved payment providers.',
                    ),
                    const SizedBox(height: 26),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(56),
                        backgroundColor: Colors.white,
                        foregroundColor: LoanHubColors.primary,
                        textStyle: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) =>
                              LoginScreen(api: api, onSignedIn: onSignedIn),
                        ),
                      ),
                      icon: const Icon(Icons.login),
                      label: const Text('SIGN IN'),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(54),
                        foregroundColor: Colors.white,
                        side: const BorderSide(
                          color: LoanHubColors.brandGreen,
                          width: 1.5,
                        ),
                      ),
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => InterestedClientSignup(
                            api: api,
                            onSignedIn: onSignedIn,
                          ),
                        ),
                      ),
                      icon: const Icon(Icons.person_add_alt_1),
                      label: const Text('I AM INTERESTED IN LOANHUB'),
                    ),
                    const SizedBox(height: 10),
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const TermsConditionsPage(),
                        ),
                      ),
                      icon: const Icon(Icons.description_outlined),
                      label: const Text('Terms & Conditions'),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'Money movements are only final after the configured payment provider confirms settlement.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Color(0xFFCBD5E1), fontSize: 11),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _LandingFeature extends StatelessWidget {
  const _LandingFeature({
    required this.icon,
    required this.title,
    required this.subtitle,
  });
  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: .10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: LoanHubColors.brandGreen.withValues(alpha: .35),
        ),
      ),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: Colors.white.withValues(alpha: .12),
            child: Icon(icon, color: const Color(0xFF8DE081)),
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: Color(0xFFDCEAF5),
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({required this.api, required this.onSignedIn, super.key});
  final LoanHubApi api;
  final Future<void> Function() onSignedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final phone = TextEditingController();
  final password = TextEditingController();
  final otp = TextEditingController();
  final server = TextEditingController(text: 'http://10.0.2.2:8000');
  bool loading = false;
  String? error;

  @override
  void dispose() {
    phone.dispose();
    password.dispose();
    otp.dispose();
    server.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await widget.api.login(
        phone: phone.text,
        password: password.text,
        otp: otp.text,
        baseUrl: server.text,
      );
      await widget.onSignedIn();
      if (mounted) Navigator.of(context).popUntil((route) => route.isFirst);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sign in to LoanHub')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(22),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Center(child: LoanHubAppIcon(size: 74, radius: 20)),
                      const SizedBox(height: 12),
                      const Text(
                        'Use any active LoanHub account',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 20),
                      TextField(
                        controller: server,
                        decoration: const InputDecoration(
                          labelText: 'LoanHub server',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: phone,
                        keyboardType: TextInputType.phone,
                        decoration: const InputDecoration(
                          labelText: 'Phone number',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: password,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'Password',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: otp,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'OTP (if required)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ],
                      const SizedBox(height: 18),
                      FilledButton.icon(
                        onPressed: loading ? null : _login,
                        icon: loading
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.login),
                        label: Text(loading ? 'SIGNING IN…' : 'SIGN IN'),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Platform owners, company users and borrowers use the same LoanHub sign-in. Calling tools appear only for eligible company roles.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 11),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class InterestedClientSignup extends StatefulWidget {
  const InterestedClientSignup({
    required this.api,
    required this.onSignedIn,
    super.key,
  });
  final LoanHubApi api;
  final Future<void> Function() onSignedIn;

  @override
  State<InterestedClientSignup> createState() => _InterestedClientSignupState();
}

class _InterestedClientSignupState extends State<InterestedClientSignup> {
  final onboarding = const MobileOnboardingApi();
  final firstName = TextEditingController();
  final lastName = TextEditingController();
  final phone = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  final server = TextEditingController(text: 'http://10.0.2.2:8000');
  bool loading = false;
  String? error;

  @override
  void dispose() {
    firstName.dispose();
    lastName.dispose();
    phone.dispose();
    email.dispose();
    password.dispose();
    server.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await onboarding.registerInterestedClient(
        baseUrl: server.text,
        firstName: firstName.text,
        lastName: lastName.text,
        phone: phone.text,
        email: email.text,
        password: password.text,
      );
      await widget.api.login(
        phone: phone.text,
        password: password.text,
        baseUrl: server.text,
      );
      await widget.onSignedIn();
      if (mounted) Navigator.of(context).popUntil((route) => route.isFirst);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Join LoanHub')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 500),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Center(child: LoanHubAppIcon(size: 76, radius: 22)),
                  const SizedBox(height: 14),
                  Text(
                    'Interested in LoanHub?',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Create a basic account to chat with LoanHub and explore services. This does not approve a loan; credit applications still require a complete borrower profile and normal assessment.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 20),
                  TextField(
                    controller: server,
                    decoration: const InputDecoration(
                      labelText: 'LoanHub server',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: firstName,
                          decoration: const InputDecoration(
                            labelText: 'First name',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextField(
                          controller: lastName,
                          decoration: const InputDecoration(
                            labelText: 'Last name',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: phone,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Phone number',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'Email (optional)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: password,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'Password (8+ characters)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: loading ? null : _create,
                    icon: loading
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.person_add),
                    label: Text(
                      loading ? 'CREATING ACCOUNT…' : 'CREATE LOANHUB ACCOUNT',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
