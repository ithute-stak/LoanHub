import 'package:flutter_test/flutter_test.dart';
import 'package:loanhub_call_mobile/realtime/realtime_event.dart';

void main() {
  test('parses typed LoanHub money event and notification route', () {
    final event = LoanHubRealtimeEvent.fromJson({
      'type': 'MONEY_RECEIVED',
      'event_id': 'event-1',
      'domain': 'money',
      'entity_id': 'payment-1',
      'data': {'amount': '150.00', 'currency': 'LSL'},
      'notification': {
        'category': 'money',
        'title': 'Money received',
        'body': 'LSL 150.00 received in LoanHub',
        'route': 'money:payment-1',
      },
    });

    expect(event.isMoney, isTrue);
    expect(event.isChat, isFalse);
    expect(event.eventId, 'event-1');
    expect(event.data['amount'], '150.00');
    expect(event.notificationCategory, 'money');
    expect(event.notificationRoute, 'money:payment-1');
  });

  test('infers legacy chat event domain', () {
    final event = LoanHubRealtimeEvent.fromJson({
      'type': 'CHAT_MESSAGE_CREATED',
      'conversation_id': 'conversation-1',
    });

    expect(event.domain, 'chat');
    expect(event.isChat, isTrue);
  });
}
