import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'api/loanhub_api.dart';
import 'features/calls/calls_page.dart';
import 'features/chats/chats_page.dart';
import 'features/explore/explore_page.dart';
import 'features/money/money_page.dart';
import 'features/operations/mobile_operations_page.dart';
import 'features/profile/profile_page.dart';
import 'layout/loanhub_responsive.dart';
import 'mobile_role_workspace.dart';
import 'realtime/chat_bloc.dart';
import 'realtime/money_bloc.dart';
import 'realtime/notification_bloc.dart';
import 'realtime/realtime_bloc.dart';
import 'realtime/realtime_repository.dart';
import 'widgets/loanhub_brand.dart';

class SuperAppHome extends StatefulWidget {
  const SuperAppHome({
    required this.api,
    required this.onSignedOut,
    required this.businessCallsBuilder,
    super.key,
  });

  final LoanHubApi api;
  final Future<void> Function() onSignedOut;
  final Widget Function(BuildContext context) businessCallsBuilder;

  @override
  State<SuperAppHome> createState() => _SuperAppHomeState();
}

class _SuperAppHomeState extends State<SuperAppHome> {
  static const _titles = ['LoanHub', 'Chats', 'Calls', 'LoanHub Money', 'You'];

  int index = 0;

  void _navigateWorkspace(MobileWorkspaceDestination destination) {
    switch (destination) {
      case MobileWorkspaceDestination.chats:
        setState(() => index = 1);
        return;
      case MobileWorkspaceDestination.calls:
        setState(() => index = 2);
        return;
      case MobileWorkspaceDestination.money:
        setState(() => index = 3);
        return;
      case MobileWorkspaceDestination.operations:
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => MobileOperationsPage(
              api: widget.api,
              onOpenCalls: () async {
                if (!mounted) return;
                Navigator.of(context).pop();
                if (mounted) setState(() => index = 2);
              },
            ),
          ),
        );
        return;
      case MobileWorkspaceDestination.profile:
        setState(() => index = 4);
        return;
      case MobileWorkspaceDestination.explore:
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => ExplorePage(api: widget.api)),
        );
        return;
    }
  }

  Future<void> _applyNotificationRoute(String route) async {
    if (!mounted) return;
    if (route.startsWith('chat:') || route == 'chats') {
      setState(() => index = 1);
      context.read<ChatBloc>().add(const ChatRefreshRequested());
    } else if (route.startsWith('money:') || route == 'money') {
      setState(() => index = 3);
      context.read<MoneyBloc>().add(const MoneyRefreshRequested());
    } else if (route.startsWith('call')) {
      setState(() => index = 2);
    }
    await widget.api.storage.delete(key: 'loanhub_pending_notification_route');
    if (mounted) {
      context.read<NotificationBloc>().add(const NotificationRouteConsumed());
    }
  }

  Future<void> _signOut() async {
    try {
      await context.read<LoanHubRealtimeRepository>().revokePushDevice();
    } catch (_) {
      // Signing out must still succeed when the device is offline.
    }
    await widget.api.logout();
    await widget.onSignedOut();
  }

  @override
  Widget build(BuildContext context) {
    final unread = context.select<ChatBloc, int>(
      (bloc) => bloc.state.unreadCount,
    );
    final connection = context.select<RealtimeBloc, RealtimeConnectionStatus>(
      (bloc) => bloc.state.connection,
    );
    final moneyEvent = context.select<MoneyBloc, String?>(
      (bloc) => bloc.state.latestMoneyEvent?.type,
    );
    final pages = [
      MobileRoleWorkspace(
        api: widget.api,
        onNavigate: _navigateWorkspace,
      ),
      ChatsPage(api: widget.api),
      CallsPage(
        api: widget.api,
        businessCallsBuilder: widget.businessCallsBuilder,
      ),
      MoneyPage(api: widget.api),
      ProfilePage(api: widget.api, onSignedOut: widget.onSignedOut),
    ];
    final width = MediaQuery.sizeOf(context).width;
    final useRail = LoanHubBreakpoints.useNavigationRail(width);

    return BlocListener<NotificationBloc, NotificationBlocState>(
      listenWhen: (previous, current) =>
          previous.revision != current.revision && current.route != null,
      listener: (context, state) {
        final route = state.route;
        if (route != null) unawaited(_applyNotificationRoute(route));
      },
      child: Scaffold(
        appBar: AppBar(
          title: Row(
            children: [
              const LoanHubAppIcon(size: 34, radius: 10),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _titles[index],
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              _RealtimeDot(status: connection),
            ],
          ),
          actions: [
            PopupMenuButton<String>(
              onSelected: (value) {
                if (value == 'channels') {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => ExplorePage(api: widget.api),
                    ),
                  );
                } else if (value == 'logout') {
                  unawaited(_signOut());
                }
              },
              itemBuilder: (_) => const [
                PopupMenuItem(
                  value: 'channels',
                  child: ListTile(
                    dense: true,
                    leading: Icon(Icons.campaign_outlined),
                    title: Text('Company channels'),
                  ),
                ),
                PopupMenuItem(
                  value: 'logout',
                  child: ListTile(
                    dense: true,
                    leading: Icon(Icons.logout),
                    title: Text('Sign out'),
                  ),
                ),
              ],
            ),
          ],
        ),
        body: useRail
            ? Row(
                children: [
                  NavigationRail(
                    extended: width >= LoanHubBreakpoints.wideTablet,
                    selectedIndex: index,
                    onDestinationSelected: (value) => setState(
                      () => index = value,
                    ),
                    labelType: width >= LoanHubBreakpoints.wideTablet
                        ? NavigationRailLabelType.none
                        : NavigationRailLabelType.all,
                    destinations: _railDestinations(unread, moneyEvent),
                  ),
                  const VerticalDivider(width: 1),
                  Expanded(child: IndexedStack(index: index, children: pages)),
                ],
              )
            : IndexedStack(index: index, children: pages),
        bottomNavigationBar: useRail
            ? null
            : NavigationBar(
                selectedIndex: index,
                labelBehavior: width < LoanHubBreakpoints.compact
                    ? NavigationDestinationLabelBehavior.onlyShowSelected
                    : NavigationDestinationLabelBehavior.alwaysShow,
                onDestinationSelected: (value) => setState(() => index = value),
                destinations: _bottomDestinations(unread, moneyEvent),
              ),
      ),
    );
  }

  List<NavigationDestination> _bottomDestinations(
    int unread,
    String? moneyEvent,
  ) => [
    const NavigationDestination(
      icon: Icon(Icons.home_outlined),
      selectedIcon: Icon(Icons.home),
      label: 'Home',
    ),
    NavigationDestination(
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text(unread > 99 ? '99+' : '$unread'),
        child: const Icon(Icons.chat_bubble_outline),
      ),
      selectedIcon: Badge(
        isLabelVisible: unread > 0,
        label: Text(unread > 99 ? '99+' : '$unread'),
        child: const Icon(Icons.chat_bubble),
      ),
      label: 'Chats',
    ),
    const NavigationDestination(
      icon: Icon(Icons.call_outlined),
      selectedIcon: Icon(Icons.call),
      label: 'Calls',
    ),
    NavigationDestination(
      icon: Badge(
        isLabelVisible: moneyEvent == 'MONEY_RECEIVED',
        child: const Icon(Icons.account_balance_wallet_outlined),
      ),
      selectedIcon: const Icon(Icons.account_balance_wallet),
      label: 'Money',
    ),
    const NavigationDestination(
      icon: Icon(Icons.person_outline),
      selectedIcon: Icon(Icons.person),
      label: 'You',
    ),
  ];

  List<NavigationRailDestination> _railDestinations(
    int unread,
    String? moneyEvent,
  ) => [
    const NavigationRailDestination(
      icon: Icon(Icons.home_outlined),
      selectedIcon: Icon(Icons.home),
      label: Text('Home'),
    ),
    NavigationRailDestination(
      icon: Badge(
        isLabelVisible: unread > 0,
        label: Text(unread > 99 ? '99+' : '$unread'),
        child: const Icon(Icons.chat_bubble_outline),
      ),
      selectedIcon: Badge(
        isLabelVisible: unread > 0,
        label: Text(unread > 99 ? '99+' : '$unread'),
        child: const Icon(Icons.chat_bubble),
      ),
      label: const Text('Chats'),
    ),
    const NavigationRailDestination(
      icon: Icon(Icons.call_outlined),
      selectedIcon: Icon(Icons.call),
      label: Text('Calls'),
    ),
    NavigationRailDestination(
      icon: Badge(
        isLabelVisible: moneyEvent == 'MONEY_RECEIVED',
        child: const Icon(Icons.account_balance_wallet_outlined),
      ),
      selectedIcon: const Icon(Icons.account_balance_wallet),
      label: const Text('Money'),
    ),
    const NavigationRailDestination(
      icon: Icon(Icons.person_outline),
      selectedIcon: Icon(Icons.person),
      label: Text('You'),
    ),
  ];
}

class _RealtimeDot extends StatelessWidget {
  const _RealtimeDot({required this.status});

  final RealtimeConnectionStatus status;

  @override
  Widget build(BuildContext context) {
    final connected = status == RealtimeConnectionStatus.connected;
    return Tooltip(
      message: connected ? 'Realtime connected' : 'Realtime reconnecting',
      child: Container(
        width: 9,
        height: 9,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: connected
              ? Colors.green
              : Theme.of(context).colorScheme.outline,
        ),
      ),
    );
  }
}
