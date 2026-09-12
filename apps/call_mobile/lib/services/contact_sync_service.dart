import 'package:flutter_contacts/flutter_contacts.dart';

class ContactSyncResult {
  const ContactSyncResult({
    required this.created,
    required this.alreadyPresent,
    required this.skippedWithoutPhone,
  });

  final int created;
  final int alreadyPresent;
  final int skippedWithoutPhone;

  int get totalProcessed => created + alreadyPresent + skippedWithoutPhone;
}

class ContactSyncService {
  Future<ContactSyncResult> syncClients(
    List<Map<String, dynamic>> clients,
  ) async {
    final permission = await FlutterContacts.permissions.request(
      PermissionType.readWrite,
    );
    if (permission != PermissionStatus.granted) {
      throw StateError(
        'Contacts permission is required to save LoanHub clients in the phone book.',
      );
    }

    final existing = await FlutterContacts.getAll(
      properties: {ContactProperty.name, ContactProperty.phone},
    );
    final existingPhones = <String>{};
    for (final contact in existing) {
      for (final phone in contact.phones) {
        final normalized = _normalize(phone.number);
        if (normalized.isNotEmpty) {
          existingPhones.add(normalized);
        }
      }
    }

    var created = 0;
    var alreadyPresent = 0;
    var skippedWithoutPhone = 0;

    for (final client in clients) {
      final phone = client['phone']?.toString().trim() ?? '';
      final normalized = _normalize(phone);
      if (normalized.isEmpty) {
        skippedWithoutPhone += 1;
        continue;
      }
      if (existingPhones.contains(normalized)) {
        alreadyPresent += 1;
        continue;
      }

      final displayName = client['name']?.toString().trim();
      final nameParts = _nameParts(
        displayName == null || displayName.isEmpty
            ? 'LoanHub Client'
            : displayName,
      );
      await FlutterContacts.create(
        Contact(
          name: Name(first: nameParts.$1, last: nameParts.$2),
          phones: [
            Phone(
              number: phone,
              label: const Label(PhoneLabel.custom, 'LoanHub Client'),
            ),
          ],
        ),
      );
      existingPhones.add(normalized);
      created += 1;
    }

    return ContactSyncResult(
      created: created,
      alreadyPresent: alreadyPresent,
      skippedWithoutPhone: skippedWithoutPhone,
    );
  }

  (String, String) _nameParts(String value) {
    final parts = value
        .split(RegExp(r'\s+'))
        .where((part) => part.trim().isNotEmpty)
        .toList();
    if (parts.isEmpty) {
      return ('LoanHub', 'Client');
    }
    if (parts.length == 1) {
      return (parts.first, '');
    }
    return (parts.first, parts.sublist(1).join(' '));
  }

  String _normalize(String value) {
    var digits = value.replaceAll(RegExp(r'\D'), '');
    if (digits.startsWith('00')) {
      digits = digits.substring(2);
    }
    if (digits.length == 8) {
      digits = '266$digits';
    }
    return digits;
  }
}
