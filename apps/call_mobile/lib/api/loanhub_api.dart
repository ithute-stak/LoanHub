import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../storage/offline_store.dart';

String _safeMobileError(String message, int? statusCode) {
  final value = message.trim();
  final lower = value.toLowerCase();
  if (statusCode == 401) {
    return 'Your session has ended. Please sign in again.';
  }
  if (statusCode == 403) {
    return 'Your account is not permitted to perform that action.';
  }
  if (statusCode == 404) {
    return 'That LoanHub record is no longer available.';
  }
  if (statusCode != null && statusCode >= 500) {
    return 'LoanHub is temporarily unavailable. Please try again shortly.';
  }
  const unsafeFragments = [
    'psycopg',
    'sqlalchemy',
    'select ',
    'insert ',
    'update ',
    'delete ',
    'traceback',
    'dataerror',
    'validationerror',
    'stack trace',
    '[parameters:',
    'uuid(',
  ];
  final looksUnsafe =
      value.length > 220 ||
      unsafeFragments.any(lower.contains) ||
      RegExp(
        r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        caseSensitive: false,
      ).hasMatch(value);
  return looksUnsafe
      ? 'LoanHub could not complete that request. Please try again shortly.'
      : value.isEmpty
      ? 'LoanHub could not complete that request. Please try again shortly.'
      : value;
}

class LoanHubApiException implements Exception {
  const LoanHubApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => _safeMobileError(message, statusCode);
}

class LoanHubApi {
  LoanHubApi({FlutterSecureStorage? storage, OfflineStore? offlineStore})
    : storage = storage ?? const FlutterSecureStorage(),
      offlineStore = offlineStore ?? OfflineStore();

  final FlutterSecureStorage storage;
  final OfflineStore offlineStore;

  static const _tokenKey = 'loanhub_access_token';
  static const _companyKey = 'loanhub_company_id';
  static const _roleKey = 'loanhub_active_role';
  static const _branchKey = 'loanhub_branch_id';
  static const _userIdKey = 'loanhub_user_id';
  static const _displayNameKey = 'loanhub_display_name';
  static const _callingEnabledKey = 'loanhub_calling_enabled';
  static const _deviceKey = 'loanhub_call_device_uuid';
  static const _baseUrlKey = 'loanhub_base_url';
  static const _compiledBaseUrl = String.fromEnvironment('LOANHUB_API_URL');
  static const _isProductBuild = bool.fromEnvironment('dart.vm.product');
  static const _developmentBaseUrl = 'http://10.0.2.2:8000';

  static const callingRoles = <String>{
    'company_owner',
    'company_admin',
    'branch_manager',
    'loan_officer',
    'collections_officer',
    'customer_support',
    'operations_officer',
    // Legacy company memberships used this owner/admin wording. The backend
    // remains the final permission check before a controlled call can start.
    'owner',
    'admin',
  };

  Future<bool> hasSession() async =>
      (await storage.read(key: _tokenKey))?.isNotEmpty == true;

  String _normalizeBaseUrl(String value) =>
      value.trim().replaceFirst(RegExp(r'/+$'), '');

  String _releaseBaseUrl() => _normalizeBaseUrl(_compiledBaseUrl);

  Future<String> baseUrl() async {
    if (_isProductBuild && _releaseBaseUrl().isNotEmpty) {
      return _releaseBaseUrl();
    }
    final value = (await storage.read(key: _baseUrlKey))?.trim();
    if (value == null || value.isEmpty) {
      return _releaseBaseUrl().isNotEmpty
          ? _releaseBaseUrl()
          : _developmentBaseUrl;
    }
    return value;
  }

  Future<void> setBaseUrl(String value) async {
    var normalized = _normalizeBaseUrl(value);
    if (_isProductBuild && _releaseBaseUrl().isNotEmpty) {
      normalized = _releaseBaseUrl();
    }
    if (_isProductBuild && !normalized.startsWith('https://')) {
      throw const LoanHubApiException(
        'This production LoanHub build requires a secure HTTPS server configuration.',
      );
    }
    await storage.write(key: _baseUrlKey, value: normalized);
  }

  Future<Map<String, dynamic>> login({
    required String phone,
    required String password,
    String? otp,
    required String baseUrl,
  }) async {
    await setBaseUrl(baseUrl);
    final response = await _request(
      'POST',
      '/auth/login',
      authenticated: false,
      body: {
        'phone': phone.trim(),
        'password': password,
        'otp': otp?.trim().isEmpty == true ? null : otp?.trim(),
        'device_name': 'LoanHub Mobile',
      },
    );
    final token = response['access_token'] as String?;
    final user = response['user'] as Map<String, dynamic>? ?? const {};
    if (token == null || token.isEmpty) {
      throw const LoanHubApiException(
        'LoanHub did not return a valid session.',
      );
    }

    final memberships = (user['memberships'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();
    Map<String, dynamic>? membership;
    for (final row in memberships) {
      if (callingRoles.contains(row['role']?.toString())) {
        membership = row;
        break;
      }
    }
    membership ??= memberships.isNotEmpty ? memberships.first : null;

    final role =
        membership?['role']?.toString() ??
        user['role']?.toString() ??
        'borrower';
    final companyId = membership?['company_id']?.toString();
    final branchId = membership?['branch_id']?.toString();
    final displayName =
        user['full_name']?.toString() ??
        user['name']?.toString() ??
        user['email']?.toString() ??
        user['phone']?.toString() ??
        'LoanHub user';

    await storage.write(key: _tokenKey, value: token);
    await storage.write(key: _roleKey, value: role);
    await storage.write(key: _userIdKey, value: user['id']?.toString());
    await storage.write(key: _displayNameKey, value: displayName);
    await storage.write(
      key: _callingEnabledKey,
      value: callingRoles.contains(role).toString(),
    );
    if (companyId?.isNotEmpty == true) {
      await storage.write(key: _companyKey, value: companyId);
    } else {
      await storage.delete(key: _companyKey);
    }
    if (branchId?.isNotEmpty == true) {
      await storage.write(key: _branchKey, value: branchId);
    } else {
      await storage.delete(key: _branchKey);
    }
    return response;
  }

  Future<Map<String, dynamic>> sessionInfo() async => {
    'user_id': await storage.read(key: _userIdKey),
    'display_name': await storage.read(key: _displayNameKey),
    'role': await storage.read(key: _roleKey) ?? 'borrower',
    'company_id': await storage.read(key: _companyKey),
    'branch_id': await storage.read(key: _branchKey),
    'calling_enabled': (await storage.read(key: _callingEnabledKey)) == 'true',
  };

  Future<bool> canUseBusinessCalling() async {
    final role = await storage.read(key: _roleKey);
    // Older releases stored calling_enabled separately. Derive the result from
    // the role as well so an eligible employee is not left on the old
    // "Contact LoanHub" screen after an app-only update.
    return callingRoles.contains(role) ||
        (await storage.read(key: _callingEnabledKey)) == 'true';
  }

  Future<void> logout() async {
    await storage.delete(key: _tokenKey);
    await storage.delete(key: _companyKey);
    await storage.delete(key: _roleKey);
    await storage.delete(key: _branchKey);
    await storage.delete(key: _userIdKey);
    await storage.delete(key: _displayNameKey);
    await storage.delete(key: _callingEnabledKey);
  }

  // Platform chat -----------------------------------------------------------

  Future<List<Map<String, dynamic>>> chatDirectory({String? search}) async {
    final query = search == null || search.trim().isEmpty
        ? ''
        : '?search=${Uri.encodeQueryComponent(search.trim())}';
    final result = await _request('GET', '/chat/directory$query');
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> chatConversations() async {
    final result = await _request('GET', '/chat/conversations');
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<int> chatUnreadCount() async {
    final result = await _request('GET', '/chat/unread-count');
    return (result['unread_count'] as num?)?.toInt() ?? 0;
  }

  Future<Map<String, dynamic>> createConversation({
    required List<String> participantIds,
    String? title,
    String conversationType = 'direct',
  }) async {
    return _request(
      'POST',
      '/chat/conversations',
      body: {
        'participant_ids': participantIds,
        'title': title,
        'conversation_type': conversationType,
      },
    );
  }

  Future<List<Map<String, dynamic>>> chatMessages(
    String conversationId, {
    int limit = 100,
  }) async {
    final result = await _request(
      'GET',
      '/chat/conversations/$conversationId/messages?limit=$limit',
    );
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> sendChatMessage(
    String conversationId,
    String body, {
    String? replyToMessageId,
  }) async {
    return _request(
      'POST',
      '/chat/conversations/$conversationId/messages',
      body: {
        'body': body.trim(),
        'client_message_id': _uuidV4(),
        'reply_to_message_id': replyToMessageId,
      },
    );
  }

  Future<void> markConversationRead(String conversationId) async {
    await _request('PATCH', '/chat/conversations/$conversationId/read');
  }

  // LoanHub Money -----------------------------------------------------------

  Future<Map<String, dynamic>> moneyConfiguration() async {
    return _request('GET', '/loanhub-money/configuration');
  }

  Future<List<Map<String, dynamic>>> moneyTransfers() async {
    final result = await _request('GET', '/loanhub-money/transfers');
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> createMoneyTransfer({
    required String transferType,
    required String amount,
    String currency = 'LSL',
    String? counterpartyPhone,
    String? counterpartyReference,
    String? note,
  }) async {
    return _request(
      'POST',
      '/loanhub-money/transfers',
      body: {
        'transfer_type': transferType,
        'amount': amount,
        'currency': currency,
        'counterparty_phone': counterpartyPhone,
        'counterparty_reference': counterpartyReference,
        'note': note,
        'idempotency_key': _uuidV4(),
      },
    );
  }

  Future<Map<String, dynamic>> gatewayConfiguration() async {
    return _request('GET', '/lelefapaygate/configuration');
  }

  Future<List<Map<String, dynamic>>> companyChannelPosts() async {
    final result = await _request('GET', '/professional/wall-posts');
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  // Business calling -------------------------------------------------------

  Future<Map<String, dynamic>> bootstrap() async {
    return _request('GET', '/call-management/mobile/bootstrap');
  }

  Future<Map<String, dynamic>> dashboard() async {
    return _request('GET', '/call-management/dashboard');
  }

  Future<List<Map<String, dynamic>>> callRecords({int limit = 60}) async {
    final result = await _request(
      'GET',
      '/call-management/calls?limit=$limit',
    );
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> clients({String? search}) async {
    final query = search == null || search.trim().isEmpty
        ? ''
        : '?search=${Uri.encodeQueryComponent(search.trim())}';
    final result = await _request('GET', '/call-management/clients$query');
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> teamDirectory() async {
    final result = await _request('GET', '/call-management/team-directory');
    return (result['__list'] as List<dynamic>).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> borrowerCallProfile(String borrowerId) async {
    return _request('GET', '/call-management/clients/$borrowerId');
  }

  Future<Map<String, dynamic>> addBorrowerCallContact(
    String borrowerId, {
    required String fullName,
    required String relationship,
    required String phone,
    bool isCallPermitted = true,
  }) async {
    return _request(
      'POST',
      '/call-management/clients/$borrowerId/contacts',
      body: {
        'full_name': fullName.trim(),
        'relationship': relationship.trim(),
        'phone': phone.trim(),
        'is_call_permitted': isCallPermitted,
      },
    );
  }

  Future<Map<String, dynamic>> registerDevice() async {
    var deviceUuid = await storage.read(key: _deviceKey);
    deviceUuid ??= _uuidV4();
    await storage.write(key: _deviceKey, value: deviceUuid);
    return _request(
      'POST',
      '/call-management/devices/register',
      body: {
        'device_uuid': deviceUuid,
        'device_name': 'LoanHub mobile',
        'platform': Platform.operatingSystem,
        'os_version': Platform.operatingSystemVersion,
        'app_version': '1.0.0',
      },
    );
  }

  Future<Map<String, dynamic>> createCall({
    required String phoneNumber,
    required String direction,
    String? borrowerId,
    String? loanId,
    String? deviceId,
  }) async {
    final idempotencyId = _uuidV4();
    final payload = <String, dynamic>{
      'device_call_uuid': idempotencyId,
      'phone_number': phoneNumber,
      'direction': direction,
      'started_at': DateTime.now().toUtc().toIso8601String(),
      'borrower_id': borrowerId,
      'loan_id': loanId,
      'device_id': deviceId,
      'status': 'started',
    };
    try {
      return await _request('POST', '/call-management/calls', body: payload);
    } on SocketException {
      await offlineStore.savePendingCall(idempotencyId, payload);
      return {
        'id': idempotencyId,
        'offline': true,
        'device_call_uuid': idempotencyId,
      };
    }
  }

  Future<Map<String, dynamic>> mediaToken(String callId) async {
    return _request('POST', '/call-management/calls/$callId/media-token');
  }

  Future<Map<String, dynamic>> dial(String callId) async {
    return _request('POST', '/call-management/calls/$callId/dial');
  }

  Future<Map<String, dynamic>> transferCall(
    String callId,
    String targetStaffId,
  ) async {
    return _request(
      'POST',
      '/call-management/calls/$callId/transfer/$targetStaffId',
    );
  }

  Future<Map<String, dynamic>> hangup(String callId) async {
    return _request('POST', '/call-management/calls/$callId/hangup');
  }

  Future<Map<String, dynamic>> updateCall(
    String callId, {
    String? status,
    String? outcome,
    String? notes,
  }) async {
    return _request(
      'PATCH',
      '/call-management/calls/$callId',
      body: {'status': ?status, 'outcome': ?outcome, 'notes': ?notes},
    );
  }

  Future<int> syncPendingCalls() async {
    if (!await hasSession() || !await canUseBusinessCalling()) return 0;
    var synced = 0;
    for (final pending in await offlineStore.pendingCalls()) {
      try {
        await _request('POST', '/call-management/calls', body: pending.payload);
        await offlineStore.removePendingCall(pending.id);
        synced += 1;
      } catch (_) {
        break;
      }
    }
    return synced;
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 15);
    try {
      final root = (await baseUrl()).replaceFirst(RegExp(r'/+$'), '');
      final request = await client.openUrl(
        method,
        Uri.parse('$root/api/v1$path'),
      );
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (authenticated) {
        final token = await storage.read(key: _tokenKey);
        final companyId = await storage.read(key: _companyKey);
        final role = await storage.read(key: _roleKey);
        if (token == null) {
          throw const LoanHubApiException('Your LoanHub session has expired.');
        }
        request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
        if (companyId?.isNotEmpty == true) {
          request.headers.set('X-Company-ID', companyId!);
        }
        if (role?.isNotEmpty == true) {
          request.headers.set('X-Active-Role', role!);
        }
      }
      if (body != null) request.add(utf8.encode(jsonEncode(body)));
      final response = await request.close().timeout(
        const Duration(seconds: 30),
      );
      final text = await utf8.decoder.bind(response).join();
      dynamic decoded;
      if (text.isNotEmpty) {
        try {
          decoded = jsonDecode(text);
        } catch (_) {
          decoded = {'detail': text};
        }
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        // Server failures can contain implementation details. Keep those details
        // out of the app while still preserving useful, user-safe 4xx messages.
        final message = response.statusCode >= 500
            ? 'LoanHub is temporarily unavailable. Please try again shortly.'
            : decoded is Map<String, dynamic>
            ? decoded['detail']?.toString() ?? 'LoanHub request failed.'
            : 'LoanHub request failed.';
        throw LoanHubApiException(message, statusCode: response.statusCode);
      }
      if (decoded is List<dynamic>) return {'__list': decoded};
      return (decoded as Map<String, dynamic>?) ?? <String, dynamic>{};
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
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-${hex.substring(20)}';
  }
}
