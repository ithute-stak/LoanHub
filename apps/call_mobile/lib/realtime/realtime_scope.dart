import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../api/loanhub_api.dart';
import 'chat_bloc.dart';
import 'money_bloc.dart';
import 'notification_bloc.dart';
import 'notification_service.dart';
import 'push_service.dart';
import 'realtime_bloc.dart';
import 'realtime_repository.dart';

class LoanHubRealtimeScope extends StatefulWidget {
  const LoanHubRealtimeScope({
    super.key,
    required this.api,
    required this.child,
  });

  final LoanHubApi api;
  final Widget child;

  @override
  State<LoanHubRealtimeScope> createState() => _LoanHubRealtimeScopeState();
}

class _LoanHubRealtimeScopeState extends State<LoanHubRealtimeScope>
    with WidgetsBindingObserver {
  late final LoanHubRealtimeRepository _repository;
  late final RealtimeBloc _realtimeBloc;
  late final ChatBloc _chatBloc;
  late final MoneyBloc _moneyBloc;
  late final NotificationBloc _notificationBloc;
  late final LoanHubPushService _pushService;
  StreamSubscription<String>? _nativeRouteSubscription;
  StreamSubscription<String>? _pushRouteSubscription;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _repository = LoanHubRealtimeRepository(widget.api);
    _realtimeBloc = RealtimeBloc(_repository)..add(const RealtimeStarted());
    _chatBloc = ChatBloc(widget.api, _repository)..add(const ChatStarted());
    _moneyBloc = MoneyBloc(widget.api, _repository)..add(const MoneyStarted());
    _notificationBloc = NotificationBloc(_repository);
    _pushService = LoanHubPushService(_repository);
    unawaited(_initialiseNotifications());
  }

  Future<void> _initialiseNotifications() async {
    final notifications = LoanHubNotificationService.instance;
    // Listen before initialization because the native bridge may already hold
    // the notification that launched this Android activity.
    _nativeRouteSubscription = notifications.routes.listen(_handleRoute);
    _pushRouteSubscription = _pushService.routes.listen(_handleRoute);
    await notifications.initialize();
    await notifications.requestPermission();
    await _pushService.initialize();

    final pending = await widget.api.storage.read(
      key: 'loanhub_pending_notification_route',
    );
    if (pending != null && pending.trim().isNotEmpty) {
      _notificationBloc.add(NotificationRouteRequested(pending));
    }
  }

  Future<void> _handleRoute(String route) async {
    final normalized = route.trim();
    if (normalized.isEmpty) return;
    _notificationBloc.add(NotificationRouteRequested(normalized));
    // Keep a recovery copy in secure storage in case Android destroys the
    // activity before the navigation BLoC consumes the tap.
    await widget.api.storage.write(
      key: 'loanhub_pending_notification_route',
      value: normalized,
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _realtimeBloc.add(const RealtimeResumed());
      _chatBloc.add(const ChatRefreshRequested());
      _moneyBloc.add(const MoneyRefreshRequested());
      return;
    }
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached ||
        state == AppLifecycleState.hidden) {
      _realtimeBloc.add(const RealtimePaused());
    }
    // Keep the socket during short inactive interruptions such as permission
    // dialogs and notification shade transitions.
  }

  @override
  Widget build(BuildContext context) {
    return RepositoryProvider.value(
      value: _repository,
      child: MultiBlocProvider(
        providers: [
          BlocProvider.value(value: _realtimeBloc),
          BlocProvider.value(value: _chatBloc),
          BlocProvider.value(value: _moneyBloc),
          BlocProvider.value(value: _notificationBloc),
        ],
        child: BlocListener<RealtimeBloc, RealtimeBlocState>(
          listenWhen: (previous, current) =>
              previous.revision != current.revision && current.latestEvent != null,
          listener: (context, state) {
            final event = state.latestEvent;
            if (event?.notification != null) {
              unawaited(LoanHubNotificationService.instance.showEvent(event!));
            }
          },
          child: widget.child,
        ),
      ),
    );
  }

  Future<void> _disposeRealtime() async {
    await _nativeRouteSubscription?.cancel();
    await _pushRouteSubscription?.cancel();
    await _pushService.dispose();
    await _chatBloc.close();
    await _moneyBloc.close();
    await _notificationBloc.close();
    await _realtimeBloc.close();
    await _repository.dispose();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_disposeRealtime());
    super.dispose();
  }
}
