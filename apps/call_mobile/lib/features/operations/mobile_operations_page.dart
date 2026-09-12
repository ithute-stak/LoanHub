import 'package:flutter/material.dart';

import '../../api/loanhub_api.dart';
import '../../theme/loanhub_theme.dart';

/// Compact mobile operations for authorised company roles.
///
/// It deliberately uses summary cards, filters and drill-down actions rather
/// than desktop-sized tables.  The detailed document workflow remains in the
/// LoanHub web application.
class MobileOperationsPage extends StatefulWidget {
  const MobileOperationsPage({
    super.key,
    required this.api,
    required this.onOpenCalls,
  });

  final LoanHubApi api;
  final Future<void> Function() onOpenCalls;

  @override
  State<MobileOperationsPage> createState() => _MobileOperationsPageState();
}

class _MobileOperationsPageState extends State<MobileOperationsPage> {
  static const _sections = <String>[
    'Overview',
    'Portfolio',
    'Follow-up',
    'Team',
    'Calls',
  ];

  String _section = 'Overview';
  String _query = '';
  bool _loading = true;
  String? _error;
  Map<String, dynamic> _dashboard = const {};
  List<Map<String, dynamic>> _clients = const [];
  List<Map<String, dynamic>> _team = const [];
  List<Map<String, dynamic>> _calls = const [];

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<dynamic>([
        widget.api.dashboard(),
        widget.api.clients(),
        widget.api.teamDirectory(),
        widget.api.callRecords(limit: 60),
      ]);
      if (!mounted) return;
      setState(() {
        _dashboard = results[0] as Map<String, dynamic>;
        _clients = List<Map<String, dynamic>>.from(results[1] as List);
        _team = List<Map<String, dynamic>>.from(results[2] as List);
        _calls = List<Map<String, dynamic>>.from(results[3] as List);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'LoanHub could not refresh this workspace. Please check your '
            'connection and try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    return Scaffold(
      appBar: AppBar(
        title: const Text('LoanHub operations'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _reload,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _reload,
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? _Failure(message: _error!, onRetry: _reload)
                  : ListView(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
                      children: [
                        const Text(
                          'Portable company workspace',
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                            color: LoanHubColors.brandNavy,
                          ),
                        ),
                        const SizedBox(height: 5),
                        const Text(
                          'Key work, borrower follow-up and controlled calls '
                          'without desktop-sized tables.',
                          style: TextStyle(color: LoanHubColors.muted),
                        ),
                        const SizedBox(height: 14),
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: _sections
                                .map(
                                  (value) => Padding(
                                    padding: const EdgeInsets.only(right: 8),
                                    child: ChoiceChip(
                                      label: Text(value),
                                      selected: _section == value,
                                      onSelected: (_) {
                                        setState(() => _section = value);
                                      },
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        if (_section == 'Overview')
                          _Overview(
                            dashboard: _dashboard,
                            clients: _clients,
                            calls: _calls,
                            onChoose: (section) {
                              setState(() => _section = section);
                            },
                            width: width,
                          ),
                        if (_section == 'Portfolio')
                          _Portfolio(
                            clients: _clients,
                            query: _query,
                            onQueryChanged: (value) {
                              setState(() => _query = value);
                            },
                            onOpenCalls: widget.onOpenCalls,
                          ),
                        if (_section == 'Follow-up')
                          _FollowUp(
                            clients: _clients,
                            onOpenCalls: widget.onOpenCalls,
                          ),
                        if (_section == 'Team')
                          _Team(team: _team),
                        if (_section == 'Calls') _CallHistory(calls: _calls),
                      ],
                    ),
        ),
      ),
    );
  }
}

class _Overview extends StatelessWidget {
  const _Overview({
    required this.dashboard,
    required this.clients,
    required this.calls,
    required this.onChoose,
    required this.width,
  });

  final Map<String, dynamic> dashboard;
  final List<Map<String, dynamic>> clients;
  final List<Map<String, dynamic>> calls;
  final ValueChanged<String> onChoose;
  final double width;

  @override
  Widget build(BuildContext context) {
    final summary = _map(dashboard['summary']);
    final loans = clients.expand((client) => _maps(client['loans'])).toList();
    final borrowers = clients.length;
    final activeLoans = loans.where((loan) {
      final status = _text(loan['status']).toLowerCase();
      return status != 'completed' && status != 'cancelled' && status != 'written_off';
    }).length;
    final overdue = loans.where(_isFollowUpLoan).length;
    final outstanding = loans.fold<double>(
      0,
      (value, loan) => value + _number(loan['balance']),
    );
    final liveCalls = _int(summary['live_calls']);
    final recordings = _int(summary['recordings_available']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _MetricGrid(
          width: width,
          metrics: [
            _Metric('Borrowers', borrowers.toString(), Icons.people_outline),
            _Metric('Active loans', activeLoans.toString(), Icons.payments_outlined),
            _Metric('Follow-up', overdue.toString(), Icons.event_note_outlined,
                warning: overdue > 0),
            _Metric('Outstanding', _money(outstanding), Icons.account_balance_wallet_outlined),
            _Metric('Live calls', liveCalls.toString(), Icons.phone_in_talk_outlined),
            _Metric('Recordings', recordings.toString(), Icons.graphic_eq_outlined),
          ],
        ),
        const SizedBox(height: 20),
        _Hero(
          borrowers: borrowers,
          overdue: overdue,
          outstanding: outstanding,
          onOpen: () => onChoose('Portfolio'),
        ),
        const SizedBox(height: 18),
        const Text(
          'Quick actions',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: LoanHubColors.brandNavy,
          ),
        ),
        const SizedBox(height: 8),
        _ActionCard(
          icon: Icons.person_search_outlined,
          title: 'Find a borrower',
          subtitle: 'View key profile, loans and permitted call contacts.',
          onTap: () => onChoose('Portfolio'),
        ),
        _ActionCard(
          icon: Icons.notifications_active_outlined,
          title: 'Collections follow-up',
          subtitle: overdue == 0
              ? 'No overdue loans are currently shown.'
              : overdue.toString() + ' overdue loan(s) need attention.',
          onTap: () => onChoose('Follow-up'),
        ),
        _ActionCard(
          icon: Icons.groups_2_outlined,
          title: 'Team directory',
          subtitle: 'See authorised colleagues and their business extensions.',
          onTap: () => onChoose('Team'),
        ),
        _ActionCard(
          icon: Icons.history_outlined,
          title: 'Call activity',
          subtitle: calls.isEmpty
              ? 'No recent calls yet.'
              : calls.length.toString() + ' recent controlled call(s).',
          onTap: () => onChoose('Calls'),
        ),
        const SizedBox(height: 12),
        const _InfoCard(
          icon: Icons.shield_outlined,
          text: 'Payments, permissions and audit rules still apply on mobile. '
              'Use the web workspace for document preparation and wide reports.',
        ),
      ],
    );
  }
}

class _Portfolio extends StatelessWidget {
  const _Portfolio({
    required this.clients,
    required this.query,
    required this.onQueryChanged,
    required this.onOpenCalls,
  });

  final List<Map<String, dynamic>> clients;
  final String query;
  final ValueChanged<String> onQueryChanged;
  final Future<void> Function() onOpenCalls;

  @override
  Widget build(BuildContext context) {
    final needle = query.trim().toLowerCase();
    final items = clients.where((client) {
      if (needle.isEmpty) return true;
      final contacts = _maps(client['contacts']);
      final haystack = [
        _text(client['full_name']),
        _text(client['phone']),
        _text(client['loan_reference']),
        contacts.map((item) => _text(item['phone'])).join(' '),
      ].join(' ').toLowerCase();
      return haystack.contains(needle);
    }).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          onChanged: onQueryChanged,
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: 'Search borrower, phone or loan reference',
          ),
        ),
        const SizedBox(height: 12),
        Text(
          items.length.toString() + ' borrower profile(s)',
          style: const TextStyle(
            color: LoanHubColors.muted,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        if (items.isEmpty)
          const _Empty(
            icon: Icons.person_search_outlined,
            title: 'No borrower matched your search',
            detail: 'Try a borrower name, permitted phone number or loan reference.',
          ),
        ...items.take(40).map(
              (client) => _BorrowerCard(
                client: client,
                onOpenCalls: onOpenCalls,
              ),
            ),
        if (items.length > 40)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: _InfoCard(
              icon: Icons.filter_list,
              text: 'Refine your search to show a smaller, safer mobile list.',
            ),
          ),
      ],
    );
  }
}

class _FollowUp extends StatelessWidget {
  const _FollowUp({required this.clients, required this.onOpenCalls});

  final List<Map<String, dynamic>> clients;
  final Future<void> Function() onOpenCalls;

  @override
  Widget build(BuildContext context) {
    final loans = <_LoanItem>[];
    for (final client in clients) {
      for (final loan in _maps(client['loans'])) {
        if (_isFollowUpLoan(loan)) loans.add(_LoanItem(client, loan));
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _InfoCard(
          icon: Icons.info_outline,
          text: 'These are compact follow-up cards. Opening Calls lets you '
              'view the permitted borrower profile and place a governed call.',
        ),
        const SizedBox(height: 12),
        if (loans.isEmpty)
          const _Empty(
            icon: Icons.task_alt_outlined,
            title: 'No follow-up loans found',
            detail: 'There are no overdue or flagged loans in the available mobile data.',
          ),
        ...loans.map(
          (item) => _LoanCard(
            borrower: item.client,
            loan: item.loan,
            onOpenCalls: onOpenCalls,
          ),
        ),
      ],
    );
  }
}

class _Team extends StatelessWidget {
  const _Team({required this.team});

  final List<Map<String, dynamic>> team;

  @override
  Widget build(BuildContext context) {
    if (team.isEmpty) {
      return const _Empty(
        icon: Icons.groups_outlined,
        title: 'No team members are available',
        detail: 'Team visibility follows company and role permissions.',
      );
    }
    return Column(
      children: team
          .map(
            (person) => Card(
              child: ListTile(
                leading: _Avatar(name: _text(person['full_name'], 'LoanHub')),
                title: Text(_text(person['full_name'], 'LoanHub team member')),
                subtitle: Text(_teamSubtitle(person)),
                trailing: _text(person['extension']).isEmpty
                    ? null
                    : Chip(label: Text('Ext. ' + _text(person['extension']))),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _CallHistory extends StatelessWidget {
  const _CallHistory({required this.calls});

  final List<Map<String, dynamic>> calls;

  @override
  Widget build(BuildContext context) {
    if (calls.isEmpty) {
      return const _Empty(
        icon: Icons.phone_missed_outlined,
        title: 'No controlled calls yet',
        detail: 'Completed company calls will appear here when your role permits.',
      );
    }
    return Column(children: calls.map((call) => _CallCard(call: call)).toList());
  }
}

class _BorrowerCard extends StatelessWidget {
  const _BorrowerCard({required this.client, required this.onOpenCalls});

  final Map<String, dynamic> client;
  final Future<void> Function() onOpenCalls;

  @override
  Widget build(BuildContext context) {
    final name = _text(client['name'], _text(client['full_name'], 'Borrower'));
    final loans = _maps(client['loans']);
    final contacts = _maps(client['contacts']);
    final balance = loans.fold<double>(
      0,
      (value, loan) => value + _number(loan['outstanding_balance'], _number(loan['balance'])),
    );
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _Avatar(name: name),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    name,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      color: LoanHubColors.brandNavy,
                    ),
                  ),
                ),
                if (_isFlaggedClient(client))
                  const Icon(Icons.priority_high, color: Colors.orange),
              ],
            ),
            const SizedBox(height: 9),
            Text(
              _text(client['phone'], 'No permitted primary phone'),
              style: const TextStyle(color: LoanHubColors.muted),
            ),
            const SizedBox(height: 7),
            Wrap(
              spacing: 7,
              runSpacing: 6,
              children: [
                Chip(label: Text(loans.length.toString() + ' loan(s)')),
                if (balance > 0) Chip(label: Text(_money(balance) + ' balance')),
                Chip(label: Text(contacts.length.toString() + ' contact(s)')),
              ],
            ),
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: onOpenCalls,
                icon: const Icon(Icons.phone_outlined),
                label: const Text('VIEW & CALL'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoanCard extends StatelessWidget {
  const _LoanCard({
    required this.borrower,
    required this.loan,
    required this.onOpenCalls,
  });

  final Map<String, dynamic> borrower;
  final Map<String, dynamic> loan;
  final Future<void> Function() onOpenCalls;

  @override
  Widget build(BuildContext context) {
    final name = _text(borrower['name'], _text(borrower['full_name'], 'Borrower'));
    final reference = _text(loan['loan_reference'], 'Loan');
    final status = _text(loan['status'], 'Follow-up');
    final balance = _number(loan['outstanding_balance'], _number(loan['balance']));
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: _Avatar(name: name),
        title: Text(name),
        subtitle: Text(reference + '\n' + status + ' · ' + _money(balance) + ' balance'),
        isThreeLine: true,
        trailing: IconButton(
          tooltip: 'Open borrower calls',
          onPressed: onOpenCalls,
          icon: const Icon(Icons.call_outlined),
        ),
      ),
    );
  }
}

class _CallCard extends StatelessWidget {
  const _CallCard({required this.call});

  final Map<String, dynamic> call;

  @override
  Widget build(BuildContext context) {
    final direction = _text(call['direction'], 'CALL').toUpperCase();
    final inbound = direction.contains('IN');
    final name = _text(call['borrower_name'], _text(call['contact_name'], 'Client'));
    final status = _text(call['status'], 'Recorded');
    final seconds = _int(call['duration_seconds']);
    final recordingData = _map(call['recording']);
    final recordingStatus = _text(
      recordingData['status'],
      _text(call['recording_status']),
    ).toLowerCase();
    final recording = recordingStatus == 'available' ||
            recordingStatus == 'ready' ||
            recordingStatus == 'completed'
        ? 'Recording ready'
        : recordingStatus.isEmpty
        ? 'No recording'
        : 'Recording ' + recordingStatus;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: LoanHubColors.primary.withValues(alpha: .1),
          child: Icon(
            inbound ? Icons.call_received_outlined : Icons.call_made_outlined,
            color: LoanHubColors.primary,
          ),
        ),
        title: Text(name),
        subtitle: Text(
          status + ' · ' + (seconds ~/ 60).toString() + 'm ' +
              (seconds % 60).toString() + 's · ' + recording,
        ),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.width, required this.metrics});

  final double width;
  final List<_Metric> metrics;

  @override
  Widget build(BuildContext context) {
    final columns = width >= 650 ? 3 : width < 300 ? 1 : 2;
    final horizontalPadding = 32.0;
    final gapSpace = 10.0 * (columns - 1);
    final itemWidth = ((width - horizontalPadding - gapSpace) / columns)
        .clamp(110.0, 280.0)
        .toDouble();
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: metrics
          .map(
            (metric) => SizedBox(
              width: itemWidth,
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(
                        metric.icon,
                        color: metric.warning ? Colors.orange : LoanHubColors.primary,
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(metric.label,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: LoanHubColors.muted,
                                )),
                            const SizedBox(height: 2),
                            Text(metric.value,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 16,
                                  color: LoanHubColors.brandNavy,
                                )),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({
    required this.borrowers,
    required this.overdue,
    required this.outstanding,
    required this.onOpen,
  });

  final int borrowers;
  final int overdue;
  final double outstanding;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: LoanHubColors.brandNavy,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.mobile_friendly, color: Colors.white),
            const SizedBox(height: 8),
            const Text(
              'Your field-ready portfolio',
              style: TextStyle(
                color: Colors.white,
                fontSize: 19,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              borrowers.toString() + ' borrowers · ' + overdue.toString() +
                  ' follow-up · ' + _money(outstanding) + ' outstanding',
              style: const TextStyle(color: Colors.white70),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: onOpen,
              icon: const Icon(Icons.people_outline),
              label: const Text('OPEN PORTFOLIO'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 9),
      child: ListTile(
        leading: Icon(icon, color: LoanHubColors.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: LoanHubColors.primary.withValues(alpha: .06),
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: LoanHubColors.primary),
            const SizedBox(width: 10),
            Expanded(child: Text(text, style: const TextStyle(color: LoanHubColors.muted))),
          ],
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.icon, required this.title, required this.detail});

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 42),
      child: Column(
        children: [
          Icon(icon, size: 46, color: LoanHubColors.muted),
          const SizedBox(height: 10),
          Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 5),
          Text(detail, textAlign: TextAlign.center, style: const TextStyle(color: LoanHubColors.muted)),
        ],
      ),
    );
  }
}

class _Failure extends StatelessWidget {
  const _Failure({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 100),
        const Icon(Icons.cloud_off_outlined, size: 60, color: LoanHubColors.muted),
        const SizedBox(height: 14),
        Text(message, textAlign: TextAlign.center),
        const SizedBox(height: 14),
        FilledButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('RETRY'),
        ),
      ],
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.name});

  final String name;

  @override
  Widget build(BuildContext context) {
    final pieces = name.trim().split(RegExp(r'\s+'));
    final initials = pieces
        .where((item) => item.isNotEmpty)
        .take(2)
        .map((item) => item.substring(0, 1).toUpperCase())
        .join();
    return CircleAvatar(
      backgroundColor: LoanHubColors.primary.withValues(alpha: .1),
      foregroundColor: LoanHubColors.primary,
      child: Text(initials.isEmpty ? 'L' : initials),
    );
  }
}

class _Metric {
  const _Metric(this.label, this.value, this.icon, {this.warning = false});

  final String label;
  final String value;
  final IconData icon;
  final bool warning;
}

class _LoanItem {
  const _LoanItem(this.client, this.loan);

  final Map<String, dynamic> client;
  final Map<String, dynamic> loan;
}

String _text(Object? value, [String fallback = '']) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? fallback : text;
}

double _number(Object? value, [double fallback = 0]) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? fallback;
}

int _int(Object? value, [int fallback = 0]) {
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? fallback;
}

Map<String, dynamic> _map(Object? value) {
  if (value is! Map) return const {};
  return Map<String, dynamic>.from(value);
}

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const [];
  return value
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}

String _money(double value) => 'LSL ' + value.toStringAsFixed(2);

String _teamSubtitle(Map<String, dynamic> person) {
  final details = <String>[
    _text(person['role']),
    _text(person['phone']),
  ].where((item) => item.isNotEmpty).toList();
  return details.isEmpty ? 'Authorised LoanHub team member' : details.join(' · ');
}

bool _isFlaggedClient(Map<String, dynamic> client) {
  return _maps(client['loans']).any(_isFollowUpLoan);
}

bool _isFollowUpLoan(Map<String, dynamic> loan) {
  final status = _text(loan['status']).toLowerCase();
  return status.contains('overdue') ||
      status.contains('arrear') ||
      status.contains('default') ||
      loan['requires_follow_up'] == true || loan['is_overdue'] == true;
}
