import 'package:flutter/material.dart';

import '../../api/loanhub_api.dart';
import '../../layout/loanhub_responsive.dart';
import '../../theme/loanhub_theme.dart';
import '../chats/chats_page.dart';

class CallsPage extends StatefulWidget {
  const CallsPage({
    required this.api,
    required this.businessCallsBuilder,
    super.key,
  });

  final LoanHubApi api;
  final Widget Function(BuildContext context) businessCallsBuilder;

  @override
  State<CallsPage> createState() => _CallsPageState();
}

class _CallsPageState extends State<CallsPage> {
  bool? callingEnabled;

  @override
  void initState() {
    super.initState();
    widget.api.canUseBusinessCalling().then((value) {
      if (mounted) setState(() => callingEnabled = value);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (callingEnabled == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: EdgeInsets.all(
        LoanHubBreakpoints.pagePadding(MediaQuery.sizeOf(context).width),
      ),
      children: [
        const SizedBox(height: 12),
        const CircleAvatar(
          radius: 42,
          backgroundColor: LoanHubColors.primary,
          foregroundColor: Colors.white,
          child: Icon(Icons.call, size: 38),
        ),
        const SizedBox(height: 16),
        Text(
          callingEnabled! ? 'LoanHub Business Calls' : 'Call LoanHub',
          textAlign: TextAlign.center,
          style: Theme.of(
            context,
          ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 8),
        Text(
          callingEnabled!
              ? 'Client-linked calling, transfers and company-controlled recording remain available in the business call workspace.'
              : 'Your account can chat and use LoanHub Money. Business calling tools appear when a company assigns you an eligible calling role.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 24),
        if (callingEnabled!)
          FilledButton.icon(
            onPressed: () => Navigator.of(
              context,
            ).push(MaterialPageRoute(builder: widget.businessCallsBuilder)),
            icon: const Icon(Icons.phone_in_talk),
            label: const Text('OPEN BUSINESS CALLS'),
          )
        else
          FilledButton.tonalIcon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => NewChatPage(api: widget.api)),
            ),
            icon: const Icon(Icons.support_agent),
            label: const Text('CONTACT LOANHUB'),
          ),
        const SizedBox(height: 18),
        const Card(
          child: ListTile(
            leading: Icon(Icons.security),
            title: Text('Calls stay under LoanHub controls'),
            subtitle: Text(
              'Recording, retention and access remain governed by company policy and the controlled calling service.',
            ),
          ),
        ),
      ],
    );
  }
}
