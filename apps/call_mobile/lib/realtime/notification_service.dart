import 'dart:async';

import 'package:flutter/services.dart';

import 'realtime_event.dart';

class LoanHubNotificationService {
  LoanHubNotificationService._();

  static final instance = LoanHubNotificationService._();
  static const _channel = MethodChannel('ls.ithute.loanhub/notifications');

  final _routes = StreamController<String>.broadcast();
  final _shownIds = <String>{};
  bool _initialised = false;

  Stream<String> get routes => _routes.stream;

  Future<void> initialize() async {
    if (_initialised) return;
    _initialised = true;
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'notificationTap') {
        final route = call.arguments?.toString().trim() ?? '';
        if (route.isNotEmpty) _routes.add(route);
      }
    });
    await _channel.invokeMethod<void>('createChannels');
    final initialRoute = await _channel.invokeMethod<String>('initialRoute');
    if (initialRoute != null && initialRoute.trim().isNotEmpty) {
      _routes.add(initialRoute.trim());
    }
  }

  Future<void> requestPermission() async {
    await _channel.invokeMethod<void>('requestPermission');
  }

  Future<void> showEvent(LoanHubRealtimeEvent event) async {
    final title = event.notificationTitle;
    final body = event.notificationBody;
    if (title == null || body == null) return;

    final id = event.eventId;
    if (id != null && id.isNotEmpty) {
      if (_shownIds.contains(id)) return;
      _shownIds.add(id);
      if (_shownIds.length > 500) _shownIds.remove(_shownIds.first);
    }

    await _channel.invokeMethod<void>('showNotification', {
      'eventId': id ?? '${event.type}-${DateTime.now().microsecondsSinceEpoch}',
      'title': title,
      'body': body,
      'category': event.notificationCategory ?? event.domain,
      'route': event.notificationRoute ?? '',
    });
  }

  Future<void> dispose() async {
    await _routes.close();
  }
}
