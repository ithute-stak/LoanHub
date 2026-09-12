import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'firebase_config.dart';
import 'realtime_event.dart';
import 'realtime_repository.dart';

@pragma('vm:entry-point')
Future<void> loanHubFirebaseBackgroundHandler(RemoteMessage message) async {
  final options = LoanHubFirebaseConfig.options;
  if (options == null) return;
  try {
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(options: options);
    }
  } catch (_) {
    // Background push is a delivery aid. Invalid/unavailable Firebase client
    // configuration must never corrupt or block the user's LoanHub session.
  }
  // Notification payloads are rendered by Android while LoanHub is in the
  // background/terminated. WorkManager performs periodic API catch-up if a
  // device or network temporarily misses a push.
}

Future<bool> initialiseLoanHubFirebase() async {
  final options = LoanHubFirebaseConfig.options;
  if (options == null) return false;
  try {
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(options: options);
    }
    FirebaseMessaging.onBackgroundMessage(loanHubFirebaseBackgroundHandler);
    return true;
  } catch (_) {
    // Foreground WSS realtime must still work if Firebase is temporarily
    // unavailable or a development build has incomplete push configuration.
    return false;
  }
}

class LoanHubPushService {
  LoanHubPushService(this.repository);

  final LoanHubRealtimeRepository repository;
  final _routes = StreamController<String>.broadcast();
  StreamSubscription<String>? _tokenSubscription;
  StreamSubscription<RemoteMessage>? _foregroundSubscription;
  StreamSubscription<RemoteMessage>? _openedSubscription;
  bool _initialised = false;

  Stream<String> get routes => _routes.stream;

  Future<void> initialize() async {
    if (_initialised || !LoanHubFirebaseConfig.configured) return;
    if (Firebase.apps.isEmpty && !await initialiseLoanHubFirebase()) return;

    try {
      final messaging = FirebaseMessaging.instance;
      await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) {
        try {
          await repository.registerPushToken(token);
        } catch (_) {
          // Re-register on token refresh/resume; push registration must not
          // block the authenticated application shell.
        }
      }
      _tokenSubscription = messaging.onTokenRefresh.listen((token) async {
        try {
          await repository.registerPushToken(token);
        } catch (_) {
          // Network recovery and the next token/session refresh retry it.
        }
      });

      _foregroundSubscription = FirebaseMessaging.onMessage.listen((message) {
        repository.ingest(_eventFromMessage(message));
      });
      _openedSubscription = FirebaseMessaging.onMessageOpenedApp.listen((message) {
        final event = _eventFromMessage(message);
        repository.ingest(event);
        final route = event.notificationRoute;
        if (route != null && route.isNotEmpty) _routes.add(route);
      });

      final initial = await messaging.getInitialMessage();
      if (initial != null) {
        final event = _eventFromMessage(initial);
        repository.ingest(event);
        final route = event.notificationRoute;
        if (route != null && route.isNotEmpty) _routes.add(route);
      }
      _initialised = true;
    } catch (_) {
      _initialised = false;
    }
  }

  LoanHubRealtimeEvent _eventFromMessage(RemoteMessage message) {
    final data = Map<String, dynamic>.from(message.data);
    final title = data['title']?.toString() ?? message.notification?.title;
    final body = data['body']?.toString() ?? message.notification?.body;
    final json = <String, dynamic>{
      'type': data['type'] ?? 'PUSH_EVENT',
      'event_id': data['event_id'] ?? message.messageId,
      'domain': data['domain'] ?? data['category'] ?? 'system',
      'entity_id': data['entity_id'],
      'data': data,
      if (title != null && body != null)
        'notification': <String, dynamic>{
          'title': title,
          'body': body,
          'category': data['category'] ?? data['domain'] ?? 'general',
          'route': data['route'] ?? '',
        },
    };
    return LoanHubRealtimeEvent.fromJson(json);
  }

  Future<void> dispose() async {
    await _tokenSubscription?.cancel();
    await _foregroundSubscription?.cancel();
    await _openedSubscription?.cancel();
    await _routes.close();
  }
}
