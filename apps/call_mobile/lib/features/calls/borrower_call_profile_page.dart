import 'package:flutter/material.dart';
import '../../api/loanhub_api.dart';

class BorrowerCallProfilePage extends StatefulWidget {
  const BorrowerCallProfilePage({required this.api, required this.borrowerId, required this.summary, required this.onCall, super.key});
  final LoanHubApi api;
  final String borrowerId;
  final Map<String, dynamic> summary;
  final Future<void> Function(Map<String, dynamic>, Map<String, dynamic>) onCall;
  @override State<BorrowerCallProfilePage> createState() => _BorrowerCallProfilePageState();
}

class _BorrowerCallProfilePageState extends State<BorrowerCallProfilePage> {
  Map<String, dynamic>? profile;
  String? error;
  @override void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() => error = null);
    try {
      final result = await widget.api.borrowerCallProfile(widget.borrowerId);
      if (mounted) setState(() => profile = result);
    } catch (_) {
      if (mounted) setState(() => error = 'Could not load this borrower profile.');
    }
  }

  Future<void> _call(Map<String, dynamic> contact, List<Map<String, dynamic>> loans) async {
    final loan = loans.length == 1 ? loans.first : await showModalBottomSheet<Map<String, dynamic>>(
      context: context, showDragHandle: true,
      builder: (context) => ListView(shrinkWrap: true, children: loans.map((loan) => ListTile(
        title: Text(loan['loan_reference']?.toString() ?? 'Loan'),
        subtitle: Text('Balance M' + (loan['balance']?.toString() ?? '0')),
        onTap: () => Navigator.pop(context, loan),
      )).toList()),
    );
    if (loan != null && mounted) await widget.onCall(contact, loan);
  }

  Future<void> _addContact() async {
    final name = TextEditingController();
    final relationship = TextEditingController();
    final phone = TextEditingController();
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add alternative contact'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: name, decoration: const InputDecoration(labelText: 'Full name')),
          TextField(controller: relationship, decoration: const InputDecoration(labelText: 'Relationship')),
          TextField(controller: phone, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Telephone number')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('CANCEL')),
          FilledButton(
            onPressed: () async {
              if (name.text.trim().isEmpty || relationship.text.trim().isEmpty || phone.text.trim().isEmpty) return;
              await widget.api.addBorrowerCallContact(widget.borrowerId, fullName: name.text, relationship: relationship.text, phone: phone.text);
              if (context.mounted) Navigator.pop(context, true);
            },
            child: const Text('SAVE'),
          ),
        ],
      ),
    );
    name.dispose(); relationship.dispose(); phone.dispose();
    if (saved == true) await _load();
  }

  @override Widget build(BuildContext context) {
    final data = profile;
    final name = data?['name']?.toString() ?? widget.summary['name']?.toString() ?? 'Borrower profile';
    if (data == null) return Scaffold(appBar: AppBar(title: Text(name)), body: Center(
      child: error == null ? const CircularProgressIndicator() : FilledButton.icon(
        onPressed: _load, icon: const Icon(Icons.refresh), label: const Text('RETRY'))));
    final contacts = (data['contacts'] as List<dynamic>? ?? const []).whereType<Map<String, dynamic>>().toList();
    final loans = (data['loans'] as List<dynamic>? ?? const []).whereType<Map<String, dynamic>>().toList();
    final calls = (data['recent_calls'] as List<dynamic>? ?? const []).whereType<Map<String, dynamic>>().toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Borrower profile')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addContact,
        icon: const Icon(Icons.person_add_alt_1),
        label: const Text('ADD CONTACT'),
      ),
      body: ListView(
      padding: const EdgeInsets.all(16), children: [
        ListTile(contentPadding: EdgeInsets.zero, leading: CircleAvatar(radius: 30, child: Text(_initials(name))),
          title: Text(name, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 20)),
          subtitle: const Text('Authorised borrower relationship')),
        _Section(title: 'Call contacts', subtitle: 'Call the borrower or an authorised alternative contact.', children: contacts.isEmpty
          ? const [ListTile(title: Text('No contact recorded'))] : contacts.map((contact) => ListTile(
            leading: CircleAvatar(child: Icon(contact['is_primary'] == true ? Icons.person : Icons.people_alt_outlined)),
            title: Text(contact['name']?.toString() ?? 'Contact'),
            subtitle: Text((contact['relationship']?.toString() ?? 'Contact') + ' · ' + (contact['phone']?.toString() ?? '')),
            trailing: IconButton(icon: const Icon(Icons.call), onPressed: contact['is_call_permitted'] == true && loans.isNotEmpty ? () => _call(contact, loans) : null),
          )).toList()),
        _Section(title: 'Loans', subtitle: 'Loans linked to your active company only.', children: loans.isEmpty
          ? const [ListTile(title: Text('No company loan found'))] : loans.map((loan) => ListTile(
            leading: const Icon(Icons.account_balance_wallet_outlined),
            title: Text(loan['loan_reference']?.toString() ?? 'Loan'),
            subtitle: Text(_sentence(loan['status']) + ' · Balance M' + (loan['balance']?.toString() ?? '0')),
          )).toList()),
        _Section(title: 'Recent calls', subtitle: 'Controlled calls and recording status.', children: calls.isEmpty
          ? const [ListTile(title: Text('No calls logged yet'))] : calls.map((call) => ListTile(
            leading: Icon(call['direction'] == 'incoming' ? Icons.call_received : Icons.call_made),
            title: Text(_sentence(call['status']) + ' · ' + (call['phone_number']?.toString() ?? '')),
            subtitle: Text(call['recording_status'] == 'available' ? 'Recording available to authorised reviewers' : 'No recording available'),
          )).toList()),
      ],
    ));
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.subtitle, required this.children});
  final String title; final String subtitle; final List<Widget> children;
  @override Widget build(BuildContext context) => Card(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Padding(padding: const EdgeInsets.fromLTRB(16,16,16,2), child: Text(title, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17))),
    Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: Text(subtitle)),
    const SizedBox(height: 6), ...children,
  ]));
}

String _initials(String value) {
  final words = value.trim().split(RegExp(r'\s+')).where((item) => item.isNotEmpty).toList();
  if (words.isEmpty) return 'LH';
  if (words.length == 1) return words.first.substring(0, words.first.length > 1 ? 2 : 1).toUpperCase();
  return (words.first[0] + words.last[0]).toUpperCase();
}
String _sentence(dynamic value) {
  final text = value?.toString().replaceAll('_', ' ') ?? 'Unknown';
  return text.isEmpty ? 'Unknown' : text[0].toUpperCase() + text.substring(1);
}
