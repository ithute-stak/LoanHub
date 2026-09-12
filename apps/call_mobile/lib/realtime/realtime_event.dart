class LoanHubRealtimeEvent {
  const LoanHubRealtimeEvent({
    required this.type,
    required this.domain,
    required this.data,
    required this.raw,
    this.eventId,
    this.entityId,
    this.occurredAt,
    this.notification,
  });

  final String type;
  final String domain;
  final String? eventId;
  final String? entityId;
  final DateTime? occurredAt;
  final Map<String, dynamic> data;
  final Map<String, dynamic> raw;
  final Map<String, dynamic>? notification;

  bool get isChat => domain == 'chat' || type.startsWith('CHAT_');
  bool get isMoney =>
      domain == 'money' || type.startsWith('MONEY_') || type.startsWith('PAYMENT_');
  bool get isCall => domain == 'call' || type.contains('CALL');
  bool get isPresence => domain == 'presence' || type.startsWith('PRESENCE_');

  String? get notificationTitle => notification?['title']?.toString();
  String? get notificationBody => notification?['body']?.toString();
  String? get notificationCategory => notification?['category']?.toString();
  String? get notificationRoute => notification?['route']?.toString();

  factory LoanHubRealtimeEvent.fromJson(Map<String, dynamic> json) {
    final type = json['type']?.toString() ?? 'UNKNOWN_EVENT';
    final inferredDomain = type.startsWith('CHAT_')
        ? 'chat'
        : type.startsWith('MONEY_') || type.startsWith('PAYMENT_')
        ? 'money'
        : type.contains('CALL')
        ? 'call'
        : type.startsWith('PRESENCE_')
        ? 'presence'
        : 'system';
    return LoanHubRealtimeEvent(
      type: type,
      domain: json['domain']?.toString() ?? inferredDomain,
      eventId: _nullableText(json['event_id']),
      entityId: _nullableText(json['entity_id']),
      occurredAt: DateTime.tryParse(json['occurred_at']?.toString() ?? ''),
      data: _map(json['data']),
      notification: json['notification'] is Map
          ? _map(json['notification'])
          : null,
      raw: Map<String, dynamic>.from(json),
    );
  }

  static Map<String, dynamic> _map(Object? value) {
    if (value is Map<String, dynamic>) return Map<String, dynamic>.from(value);
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    return const <String, dynamic>{};
  }

  static String? _nullableText(Object? value) {
    final text = value?.toString().trim() ?? '';
    return text.isEmpty ? null : text;
  }
}
