import 'package:flutter/material.dart';

import 'api/loanhub_api.dart';
import 'layout/loanhub_responsive.dart';
import 'theme/loanhub_theme.dart';

/// Destinations exposed by the mobile shell. The server remains responsible for
/// authorisation; this mapping only keeps each role's phone workspace focused.
enum MobileWorkspaceDestination { chats, calls, money, explore, operations, profile }

class MobileRoleWorkspace extends StatefulWidget {
  const MobileRoleWorkspace({
    required this.api,
    required this.onNavigate,
    this.initialSession,
    super.key,
  });

  final LoanHubApi api;
  final ValueChanged<MobileWorkspaceDestination> onNavigate;

  /// Used only by widget tests and makes compact-device coverage deterministic.
  final Map<String, dynamic>? initialSession;

  @override
  State<MobileRoleWorkspace> createState() => _MobileRoleWorkspaceState();
}

class _MobileRoleWorkspaceState extends State<MobileRoleWorkspace> {
  Map<String, dynamic>? session;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    if (widget.initialSession != null) {
      session = widget.initialSession;
      loading = false;
    } else {
      _load();
    }
  }

  Future<void> _load() async {
    if (mounted) setState(() => loading = true);
    try {
      final value = await widget.api.sessionInfo();
      if (mounted) setState(() => session = value);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading && session == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final activeSession = session ?? const <String, dynamic>{};
    final role = activeSession['role']?.toString() ?? 'borrower';
    final name = activeSession['display_name']?.toString() ?? 'LoanHub user';
    final definition = MobileRoleDefinition.forRole(role);
    final width = MediaQuery.sizeOf(context).width;
    final padding = LoanHubBreakpoints.pagePadding(width);
    final columns = width < 390 ? 1 : width < 700 ? 2 : 3;
    final contentWidth = (width - (padding * 2)).clamp(0.0, 920.0).toDouble();
    final cardWidth =
        (contentWidth - (12 * (columns - 1))) / columns;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: EdgeInsets.all(padding),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _RoleHeader(name: name, definition: definition),
                  const SizedBox(height: 18),
                  Text(
                    'Your mobile workspace',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    definition.mobileSummary,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: definition.actions
                        .map(
                          (action) => SizedBox(
                            width: cardWidth,
                            child: _RoleActionCard(
                              action: action,
                              onTap: () => widget.onNavigate(action.destination),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                  if (_hasPortableOperations(role)) ...[
                    const SizedBox(height: 18),
                    Card(
                      child: ListTile(
                        leading: const Icon(
                          Icons.workspaces_outline,
                          color: LoanHubColors.primary,
                        ),
                        title: const Text(
                          'Portable operations',
                          style: TextStyle(fontWeight: FontWeight.w900),
                        ),
                        subtitle: const Text(
                          'Borrowers, loans, follow-up, team and compact call activity.',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => widget.onNavigate(
                          MobileWorkspaceDestination.operations,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 18),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.verified_user_outlined,
                            color: LoanHubColors.primary,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Access stays under LoanHub control',
                                  style: TextStyle(fontWeight: FontWeight.w900),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  definition.accessNote,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.desktop_windows_outlined),
                      title: const Text('Desktop companion'),
                      subtitle: Text(definition.desktopNote),
                      trailing: const Icon(Icons.lock_outline),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoleHeader extends StatelessWidget {
  const _RoleHeader({required this.name, required this.definition});

  final String name;
  final MobileRoleDefinition definition;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [LoanHubColors.brandNavy, LoanHubColors.primary],
        ),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 25,
            backgroundColor: Colors.white.withValues(alpha: .16),
            foregroundColor: Colors.white,
            child: Icon(definition.icon, size: 27),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Welcome, $name',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  definition.title,
                  style: const TextStyle(
                    color: Color(0xFFAEE6FF),
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  definition.description,
                  style: const TextStyle(color: Colors.white70, height: 1.35),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RoleActionCard extends StatelessWidget {
  const _RoleActionCard({required this.action, required this.onTap});

  final MobileRoleAction action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: action.title,
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 126),
            child: Padding(
              padding: const EdgeInsets.all(15),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(action.icon, color: LoanHubColors.primary),
                  const SizedBox(height: 20),
                  Text(
                    action.title,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    action.subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall,
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

class MobileRoleAction {
  const MobileRoleAction({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.destination,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final MobileWorkspaceDestination destination;
}

class MobileRoleDefinition {
  const MobileRoleDefinition({
    required this.title,
    required this.description,
    required this.mobileSummary,
    required this.accessNote,
    required this.desktopNote,
    required this.icon,
    required this.actions,
  });

  final String title;
  final String description;
  final String mobileSummary;
  final String accessNote;
  final String desktopNote;
  final IconData icon;
  final List<MobileRoleAction> actions;

  static MobileRoleDefinition forRole(String value) {
    final role = value.trim().toLowerCase();
    if (const {'company_owner', 'owner', 'company_admin', 'admin'}
        .contains(role)) {
      return const MobileRoleDefinition(
        title: 'Company leadership',
        description:
            'See the company pulse, reach clients securely and act on approved operational work from your phone.',
        mobileSummary:
            'Client communication, money activity, company channels and your protected account are available here.',
        accessNote:
            'Sensitive company configuration, retention controls and deletions remain protected by role and server policy.',
        desktopNote:
            'Use the LoanHub web workspace for detailed reporting, company setup and larger approval queues.',
        icon: Icons.business_center_outlined,
        actions: [
          MobileRoleAction(
            title: 'Borrower calls',
            subtitle: 'Open permitted borrower profiles and call work.',
            icon: Icons.call_outlined,
            destination: MobileWorkspaceDestination.calls,
          ),
          MobileRoleAction(
            title: 'Money activity',
            subtitle: 'View or create provider-confirmed transfer instructions.',
            icon: Icons.account_balance_wallet_outlined,
            destination: MobileWorkspaceDestination.money,
          ),
          MobileRoleAction(
            title: 'Company chat',
            subtitle: 'Stay in touch with clients and staff in realtime.',
            icon: Icons.chat_bubble_outline,
            destination: MobileWorkspaceDestination.chats,
          ),
          MobileRoleAction(
            title: 'Company channels',
            subtitle: 'Review published offers and adverts.',
            icon: Icons.campaign_outlined,
            destination: MobileWorkspaceDestination.explore,
          ),
        ],
      );
    }
    if (role == 'branch_manager') {
      return const MobileRoleDefinition(
        title: 'Branch management',
        description:
            'Run the day-to-day branch view: client contact, team communication and controlled money work.',
        mobileSummary:
            'Use this phone workspace for urgent branch actions without exposing the full desktop back office.',
        accessNote:
            'LoanHub checks your branch, company and role before every data request or action.',
        desktopNote:
            'Use web LoanHub for wide portfolio review, staff administration and detailed branch reporting.',
        icon: Icons.account_tree_outlined,
        actions: [
          MobileRoleAction(
            title: 'Client & loan calls',
            subtitle: 'Open authorised borrower contacts and linked loans.',
            icon: Icons.call_outlined,
            destination: MobileWorkspaceDestination.calls,
          ),
          MobileRoleAction(
            title: 'Branch messages',
            subtitle: 'Coordinate securely with staff and clients.',
            icon: Icons.forum_outlined,
            destination: MobileWorkspaceDestination.chats,
          ),
          MobileRoleAction(
            title: 'Money desk',
            subtitle: 'See current transfer activity and settlement state.',
            icon: Icons.payments_outlined,
            destination: MobileWorkspaceDestination.money,
          ),
        ],
      );
    }
    if (const {'loan_officer', 'collections_officer'}.contains(role)) {
      final collections = role == 'collections_officer';
      return MobileRoleDefinition(
        title: collections ? 'Collections workspace' : 'Loan officer workspace',
        description: collections
            ? 'Work borrower follow-ups, permitted contacts and controlled call notes while away from the branch.'
            : 'Work borrower relationships, loan-linked contact and secure follow-up from your phone.',
        mobileSummary:
            'The mobile workspace focuses on the next client conversation and the information you need before it.',
        accessNote:
            'Calls only use permitted contacts; LoanHub records the employee, borrower and related loan.',
        desktopNote:
            'Use web LoanHub for full application capture, calculators, approval packs and portfolio analysis.',
        icon: collections ? Icons.assignment_late_outlined : Icons.badge_outlined,
        actions: [
          const MobileRoleAction(
            title: 'Borrower calls',
            subtitle: 'Search authorised borrowers, contacts and loans.',
            icon: Icons.call_outlined,
            destination: MobileWorkspaceDestination.calls,
          ),
          const MobileRoleAction(
            title: 'Secure follow-up',
            subtitle: 'Message a client or team member in realtime.',
            icon: Icons.chat_bubble_outline,
            destination: MobileWorkspaceDestination.chats,
          ),
          const MobileRoleAction(
            title: 'Payment activity',
            subtitle: 'See settlement activity without treating pending money as received.',
            icon: Icons.receipt_long_outlined,
            destination: MobileWorkspaceDestination.money,
          ),
        ],
      );
    }
    if (const {'cashier', 'accountant', 'finance_officer'}.contains(role)) {
      return const MobileRoleDefinition(
        title: 'Finance workspace',
        description:
            'Keep payment communication and provider-confirmed money activity close while you are away from the desk.',
        mobileSummary:
            'Your mobile view prioritises settlement status, secure conversations and account safety.',
        accessNote:
            'Money actions remain provider-confirmed, audited and limited to permissions granted by the company.',
        desktopNote:
            'Use web LoanHub for reconciliation, accounting, expenses, registers and full reports.',
        icon: Icons.account_balance_outlined,
        actions: [
          MobileRoleAction(
            title: 'Money activity',
            subtitle: 'Review transfer states and create allowed instructions.',
            icon: Icons.account_balance_wallet_outlined,
            destination: MobileWorkspaceDestination.money,
          ),
          MobileRoleAction(
            title: 'Secure messages',
            subtitle: 'Resolve payment queries with authorised parties.',
            icon: Icons.chat_bubble_outline,
            destination: MobileWorkspaceDestination.chats,
          ),
          MobileRoleAction(
            title: 'Your security',
            subtitle: 'Review account and notification controls.',
            icon: Icons.lock_outline,
            destination: MobileWorkspaceDestination.profile,
          ),
        ],
      );
    }
    if (const {'customer_support', 'operations_officer'}.contains(role)) {
      return const MobileRoleDefinition(
        title: 'Operations & support',
        description:
            'Respond to LoanHub people, keep communications moving and use controlled calling where the company enables it.',
        mobileSummary:
            'This view brings secure conversations, permitted calls and public company information together.',
        accessNote:
            'You only see records and contacts the active company and your role permit.',
        desktopNote:
            'Use web LoanHub for workflow configuration, reports, escalations and administration.',
        icon: Icons.support_agent_outlined,
        actions: [
          MobileRoleAction(
            title: 'Secure conversations',
            subtitle: 'Reply to LoanHub people and company conversations.',
            icon: Icons.forum_outlined,
            destination: MobileWorkspaceDestination.chats,
          ),
          MobileRoleAction(
            title: 'Client calling',
            subtitle: 'Open controlled calls if your company subscription permits it.',
            icon: Icons.call_outlined,
            destination: MobileWorkspaceDestination.calls,
          ),
          MobileRoleAction(
            title: 'Company channels',
            subtitle: 'View published LoanHub offers and adverts.',
            icon: Icons.campaign_outlined,
            destination: MobileWorkspaceDestination.explore,
          ),
        ],
      );
    }
    if (const {'platform_owner', 'platform_admin', 'super_admin'}
        .contains(role)) {
      return const MobileRoleDefinition(
        title: 'LoanHub platform workspace',
        description:
            'Keep an executive mobile view of customer communication, platform money activity and account protection.',
        mobileSummary:
            'The mobile view is intentionally concise; tenancy, configuration and operational controls remain server governed.',
        accessNote:
            'No company data is granted by the phone UI. LoanHub checks the active role and tenant on every request.',
        desktopNote:
            'Use web LoanHub for platform administration, audit review, service configuration and detailed analytics.',
        icon: Icons.admin_panel_settings_outlined,
        actions: [
          MobileRoleAction(
            title: 'Platform messages',
            subtitle: 'Handle secure conversations from the field.',
            icon: Icons.chat_bubble_outline,
            destination: MobileWorkspaceDestination.chats,
          ),
          MobileRoleAction(
            title: 'Money activity',
            subtitle: 'View provider-confirmed LoanHub Money activity.',
            icon: Icons.account_balance_wallet_outlined,
            destination: MobileWorkspaceDestination.money,
          ),
          MobileRoleAction(
            title: 'Company channels',
            subtitle: 'Review verified company offers and adverts.',
            icon: Icons.campaign_outlined,
            destination: MobileWorkspaceDestination.explore,
          ),
        ],
      );
    }
    return const MobileRoleDefinition(
      title: 'Borrower workspace',
      description:
          'Follow your LoanHub relationship: communicate securely, discover verified offers and manage available money activity.',
      mobileSummary:
          'The mobile experience keeps your personal actions clear and never exposes another company’s private records.',
      accessNote:
          'LoanHub only shows you the companies, offers, conversations and money actions your account is authorised to use.',
      desktopNote:
          'Use web LoanHub when you need a larger screen for applications, documents and detailed repayment information.',
      icon: Icons.person_outline,
      actions: [
        MobileRoleAction(
          title: 'My messages',
          subtitle: 'Chat securely with LoanHub and participating businesses.',
          icon: Icons.chat_bubble_outline,
          destination: MobileWorkspaceDestination.chats,
        ),
        MobileRoleAction(
          title: 'Loan offers',
          subtitle: 'Browse verified company channels and adverts.',
          icon: Icons.explore_outlined,
          destination: MobileWorkspaceDestination.explore,
        ),
        MobileRoleAction(
          title: 'Money activity',
          subtitle: 'Use available, provider-confirmed LoanHub Money actions.',
          icon: Icons.account_balance_wallet_outlined,
          destination: MobileWorkspaceDestination.money,
        ),
        MobileRoleAction(
          title: 'My account',
          subtitle: 'Review your device, notification and privacy settings.',
          icon: Icons.person_outline,
          destination: MobileWorkspaceDestination.profile,
        ),
      ],
    );
  }
}


bool _hasPortableOperations(String role) {
  return const {
    'company_owner',
    'owner',
    'company_admin',
    'admin',
    'branch_manager',
    'loan_officer',
    'collections_officer',
    'customer_support',
    'operations_officer',
  }.contains(role.trim().toLowerCase());
}
