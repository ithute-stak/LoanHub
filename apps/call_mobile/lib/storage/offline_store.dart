import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Encrypted local queue for call metadata awaiting synchronization.
/// This is scoped to the device; the API's device_call_uuid is the
/// idempotency key when a queued request is retried.
class OfflineStore {
  OfflineStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'loanhub_pending_mobile_calls';
  final FlutterSecureStorage _storage;

  Future<List<PendingCall>> pendingCalls() async {
    final saved = await _storage.read(key: _key);
    if (saved == null || saved.isEmpty) return <PendingCall>[];
    final entries = jsonDecode(saved);
    if (entries is! List) return <PendingCall>[];
    return entries.whereType<Map>().map((row) {
      final payload = Map<String, dynamic>.from(row['payload'] as Map);
      return PendingCall(row['id'].toString(), payload);
    }).toList(growable: false);
  }

  Future<void> savePendingCall(
    String id,
    Map<String, dynamic> payload,
  ) async {
    final current = await pendingCalls();
    final next = <PendingCall>[
      ...current.where((call) => call.id != id),
      PendingCall(id, Map<String, dynamic>.from(payload)),
    ];
    await _write(next);
  }

  Future<void> removePendingCall(String id) async {
    final current = await pendingCalls();
    await _write(current.where((call) => call.id != id).toList());
  }

  Future<void> _write(List<PendingCall> calls) async {
    await _storage.write(
      key: _key,
      value: jsonEncode([
        for (final call in calls)
          {'id': call.id, 'payload': call.payload},
      ]),
    );
  }
}

class PendingCall {
  const PendingCall(this.id, this.payload);

  final String id;
  final Map<String, dynamic> payload;
}
