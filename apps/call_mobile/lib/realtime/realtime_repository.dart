import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../api/loanhub_api.dart';
import 'realtime_event.dart';

enum RealtimeConnectionStatus { stopped, connecting, connected, reconnecting }

class LoanHubRealtimeRepository {
  LoanHubRealtimeRepository(this.api);

  final LoanHubApi api;
  final _events = StreamController<LoanHubRealtimeEvent>.broadcast();
  final _connection = StreamController<RealtimeConnectionStatus>.broadcast();
  final _seenEventIds = <String>{};

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _socketSubscription;
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  bool _shouldRun = false;
  int _reconnectAttempt = 0;

  Stream<LoanHubRealtimeEvent> get events => _events.stream;
  Stream<RealtimeConnectionStatus> get connection => _connection.stream;

  Future<void> start() async {
    if (_shouldRun) return;
    _shouldRun = true;
    _reconnectAttempt = 0;
    await _connect();
  }

  Future<void> resume() async {
    _shouldRun = true;
    if (_channel == null) await _connect(reconnecting: true);
  }

  Future<void> pause() async {
    // Background delivery is handed to FCM. Close the foreground socket so
    // Android is free to suspend the process without a fake keep-alive claim.
    _shouldRun = false;
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    await _socketSubscription?.cancel();
    _socketSubscription = null;
    await _channel?.sink.close();
    _channel = null;
    _connection.add(RealtimeConnectionStatus.stopped);
  }

  Future<void> stop() => pause();

  Future<void> _connect({bool reconnecting = false}) async {
    if (!_shouldRun || !await api.hasSession()) return;
    _connection.add(
      reconnecting
          ? RealtimeConnectionStatus.reconnecting
          : RealtimeConnectionStatus.connecting,
    );

    final token = await api.storage.read(key: 'loanhub_access_token');
    if (token == null || token.isEmpty) {
      _connection.add(RealtimeConnectionStatus.stopped);
      return;
    }
    final companyId = await api.storage.read(key: 'loanhub_company_id');
    final deviceUuid = await ensureDeviceUuid();
    final uri = await _socketUri(
      companyId: companyId,
      clientId: 'mobile-$deviceUuid',
    );

    try {
      final channel = IOWebSocketChannel.connect(
        uri,
        protocols: <String>['loanhub.v1', 'loanhub.jwt.$token'],
        pingInterval: const Duration(seconds: 30),
        connectTimeout: const Duration(seconds: 15),
      );
      await channel.ready;
      if (!_shouldRun) {
        await channel.sink.close();
        return;
      }
      _channel = channel;
      _reconnectAttempt = 0;
      _connection.add(RealtimeConnectionStatus.connected);
      _socketSubscription = channel.stream.listen(
        _handleSocketPayload,
        onError: (_) => _socketEnded(),
        onDone: _socketEnded,
        cancelOnError: true,
      );
      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(const Duration(seconds: 25), (_) {
        if (_channel != null) _channel!.sink.add('ping');
      });
    } catch (_) {
      _channel = null;
      _scheduleReconnect();
    }
  }

  void _handleSocketPayload(dynamic payload) {
    if (payload is! String || payload == 'pong') return;
    try {
      final decoded = jsonDecode(payload);
      if (decoded is Map<String, dynamic>) {
        ingest(LoanHubRealtimeEvent.fromJson(decoded));
      } else if (decoded is Map) {
        ingest(
          LoanHubRealtimeEvent.fromJson(
            decoded.map((key, value) => MapEntry(key.toString(), value)),
          ),
        );
      }
    } catch (_) {
      // An invalid event must not tear down the shared socket.
    }
  }

  void ingest(LoanHubRealtimeEvent event) {
    final id = event.eventId;
    if (id != null && id.isNotEmpty) {
      if (_seenEventIds.contains(id)) return;
      _seenEventIds.add(id);
      if (_seenEventIds.length > 1000) {
        _seenEventIds.remove(_seenEventIds.first);
      }
    }
    _events.add(event);
  }

  void send(Map<String, dynamic> event) {
    final channel = _channel;
    if (channel == null) return;
    channel.sink.add(jsonEncode(event));
  }

  void _socketEnded() {
    _pingTimer?.cancel();
    _socketSubscription = null;
    _channel = null;
    if (_shouldRun) _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (!_shouldRun) return;
    _connection.add(RealtimeConnectionStatus.reconnecting);
    _reconnectTimer?.cancel();
    final seconds = min(30, pow(2, min(_reconnectAttempt, 5)).toInt());
    _reconnectAttempt += 1;
    _reconnectTimer = Timer(Duration(seconds: seconds), () {
      _connect(reconnecting: true);
    });
  }

  Future<Uri> _socketUri({
    required String clientId,
    String? companyId,
  }) async {
    final root = Uri.parse((await api.baseUrl()).replaceFirst(RegExp(r'/+$'), ''));
    final query = <String, String>{'client_id': clientId};
    if (companyId != null && companyId.isNotEmpty) {
      query['company_id'] = companyId;
    }
    return root.replace(
      scheme: root.scheme == 'https' ? 'wss' : 'ws',
      path: '${root.path}/api/v1/ws'.replaceAll('//', '/'),
      queryParameters: query,
    );
  }

  Future<String> ensureDeviceUuid() async {
    const key = 'loanhub_call_device_uuid';
    var value = await api.storage.read(key: key);
    if (value != null && value.isNotEmpty) return value;
    value = _uuidV4();
    await api.storage.write(key: key, value: value);
    return value;
  }

  Future<void> registerPushToken(
    String token, {
    String platform = 'android',
    String provider = 'fcm',
    String appVersion = '1.0.0',
  }) async {
    if (token.trim().isEmpty || !await api.hasSession()) return;
    await _authenticatedJsonRequest(
      'POST',
      '/realtime/devices/register',
      body: {
        'device_uuid': await ensureDeviceUuid(),
        'push_token': token.trim(),
        'platform': platform,
        'provider': provider,
        'app_version': appVersion,
      },
    );
  }

  Future<void> revokePushDevice() async {
    if (!await api.hasSession()) return;
    final deviceUuid = await ensureDeviceUuid();
    await _authenticatedJsonRequest(
      'DELETE',
      '/realtime/devices/${Uri.encodeComponent(deviceUuid)}',
    );
  }

  Future<void> _authenticatedJsonRequest(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final token = await api.storage.read(key: 'loanhub_access_token');
    if (token == null || token.isEmpty) return;
    final companyId = await api.storage.read(key: 'loanhub_company_id');
    final role = await api.storage.read(key: 'loanhub_active_role');
    final root = (await api.baseUrl()).replaceFirst(RegExp(r'/+$'), '');
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 15);
    try {
      final request = await client.openUrl(
        method,
        Uri.parse('$root/api/v1$path'),
      );
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      if (companyId?.isNotEmpty == true) {
        request.headers.set('X-Company-ID', companyId!);
      }
      if (role?.isNotEmpty == true) {
        request.headers.set('X-Active-Role', role!);
      }
      if (body != null) request.add(utf8.encode(jsonEncode(body)));
      final response = await request.close().timeout(const Duration(seconds: 30));
      await response.drain<void>();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException('LoanHub realtime registration failed (${response.statusCode}).');
      }
    } finally {
      client.close(force: true);
    }
  }

  String _uuidV4() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  Future<void> dispose() async {
    await stop();
    await _events.close();
    await _connection.close();
  }
}
