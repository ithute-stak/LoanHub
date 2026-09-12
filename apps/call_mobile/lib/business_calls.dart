import 'dart:async';

import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart';

import 'api/loanhub_api.dart';
import 'features/calls/borrower_call_profile_page.dart';
import 'layout/loanhub_responsive.dart';
import 'theme/loanhub_theme.dart';

class BusinessCallsWorkspace extends StatefulWidget {
  const BusinessCallsWorkspace({required this.api, super.key});
  final LoanHubApi api;

  @override
  State<BusinessCallsWorkspace> createState() => _BusinessCallsWorkspaceState();
}

class _BusinessCallsWorkspaceState extends State<BusinessCallsWorkspace> {
  final search = TextEditingController();
  Map<String, dynamic>? bootstrap;
  Map<String, dynamic>? dashboard;
  Map<String, dynamic>? device;
  List<Map<String, dynamic>> clients = const [];
  List<Map<String, dynamic>> team = const [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      await widget.api.syncPendingCalls();
      final values = await Future.wait([
        widget.api.bootstrap(),
        widget.api.dashboard(),
        widget.api.registerDevice(),
        widget.api.clients(search: search.text),
        widget.api.teamDirectory(),
      ]);
      if (!mounted) return;
      setState(() {
        bootstrap = values[0] as Map<String, dynamic>;
        dashboard = values[1] as Map<String, dynamic>;
        device = values[2] as Map<String, dynamic>;
        clients = values[3] as List<Map<String, dynamic>>;
        team = values[4] as List<Map<String, dynamic>>;
      });
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not load business calls. Please retry.');
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _search() async {
    try {
      final rows = await widget.api.clients(search: search.text);
      if (mounted) setState(() => clients = rows);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(
          const SnackBar(
            content: Text('Could not update the client search. Please retry.'),
          ),
        );
      }
    }
  }

  Future<void> _call(
    Map<String, dynamic> client,
    Map<String, dynamic> loan,
  ) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ActiveBusinessCallPage(
          api: widget.api,
          client: client,
          loan: loan,
          deviceId: device?['id']?.toString(),
          policy: bootstrap?['policy'] as Map<String, dynamic>? ?? const {},
          team: team,
        ),
      ),
    );
    await _load();
  }

  Future<void> _openBorrower(Map<String, dynamic> client) async {
    final borrowerId = client['borrower_id']?.toString();
    if (borrowerId == null || borrowerId.isEmpty) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => BorrowerCallProfilePage(
          api: widget.api,
          borrowerId: borrowerId,
          summary: client,
          onCall: (contact, loan) => _call(
            {...client, 'phone': contact['phone'], 'name': contact['name']},
            loan,
          ),
        ),
      ),
    );
    if (mounted) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final summary = dashboard?['summary'] as Map<String, dynamic>?;
    final policy = bootstrap?['policy'] as Map<String, dynamic>?;
    final media = bootstrap?['media'] as Map<String, dynamic>?;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Business calls'),
        actions: [
          IconButton(
            onPressed: loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: loading && bootstrap == null
          ? const Center(child: CircularProgressIndicator())
          : error != null && bootstrap == null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(error!, textAlign: TextAlign.center),
              ),
            )
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: EdgeInsets.all(
                  LoanHubBreakpoints.pagePadding(
                    MediaQuery.sizeOf(context).width,
                  ),
                ),
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _SummaryCard(
                          label: 'Today',
                          value: summary?['today_calls'] ?? 0,
                          icon: Icons.call,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _SummaryCard(
                          label: 'Recorded',
                          value: summary?['recordings_available'] ?? 0,
                          icon: Icons.mic,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Card(
                    child: ListTile(
                      leading: Icon(
                        media?['configured'] == true
                            ? Icons.cloud_done
                            : Icons.cloud_off,
                      ),
                      title: Text(
                        media?['configured'] == true
                            ? 'Controlled calling connected'
                            : 'Calling provider not configured',
                      ),
                      subtitle: Text(
                        policy?['recording_enabled'] == true
                            ? 'Company recording policy enabled'
                            : 'Recording disabled by company policy',
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: search,
                    onSubmitted: (_) => _search(),
                    decoration: InputDecoration(
                      hintText: 'Search client, phone or loan',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: IconButton(
                        onPressed: _search,
                        icon: const Icon(Icons.arrow_forward),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  if (clients.isEmpty)
                    const Card(child: ListTile(title: Text('No clients found')))
                  else
                    ...clients.map((client) {
                      final loans =
                          (client['loans'] as List<dynamic>? ?? const [])
                              .whereType<Map<String, dynamic>>()
                              .toList();
                      return Card(
                        child: ExpansionTile(
                          leading: const CircleAvatar(
                            child: Icon(Icons.person),
                          ),
                          title: Text(
                            client['name']?.toString() ?? 'Client',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          subtitle: Text(
                            '${client['phone'] ?? 'No phone'} · ${loans.length} loan(s)',
                          ),
                          children: [
                            ListTile(
                              leading: const Icon(Icons.badge_outlined),
                              title: const Text('Open borrower profile'),
                              subtitle: const Text('Loans, authorised call contacts and call history'),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () => _openBorrower(client),
                            ),
                            ...loans
                              .map(
                                (loan) => ListTile(
                                  title: Text(
                                    loan['loan_reference']?.toString() ??
                                        'Loan',
                                  ),
                                  subtitle: Text(
                                    '${loan['status'] ?? ''} · Balance M${loan['balance'] ?? 0}',
                                  ),
                                  trailing: FilledButton.icon(
                                    onPressed: client['phone'] == null
                                        ? null
                                        : () => _call(client, loan),
                                    icon: const Icon(Icons.call, size: 17),
                                    label: const Text('CALL'),
                                  ),
                                ),
                              )
                              .toList(),
                          ],
                        ),
                      );
                    }),
                ],
              ),
            ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
    required this.icon,
  });
  final String label;
  final dynamic value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon),
            const SizedBox(height: 10),
            Text(
              '$value',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
            Text(label),
          ],
        ),
      ),
    );
  }
}

class ActiveBusinessCallPage extends StatefulWidget {
  const ActiveBusinessCallPage({
    required this.api,
    required this.client,
    required this.loan,
    required this.deviceId,
    required this.policy,
    required this.team,
    super.key,
  });

  final LoanHubApi api;
  final Map<String, dynamic> client;
  final Map<String, dynamic> loan;
  final String? deviceId;
  final Map<String, dynamic> policy;
  final List<Map<String, dynamic>> team;

  @override
  State<ActiveBusinessCallPage> createState() => _ActiveBusinessCallPageState();
}

class _ActiveBusinessCallPageState extends State<ActiveBusinessCallPage> {
  Room? room;
  String? callId;
  String stage = 'Preparing secure business call…';
  String? error;
  bool muted = false;
  bool onHold = false;
  bool ending = false;
  bool completed = false;
  bool transferred = false;
  int seconds = 0;
  Timer? timer;
  String outcome = 'payment_promise';
  final notes = TextEditingController();

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void dispose() {
    timer?.cancel();
    notes.dispose();
    final activeRoom = room;
    if (activeRoom != null) {
      unawaited(activeRoom.disconnect());
      unawaited(activeRoom.dispose());
    }
    super.dispose();
  }

  Future<void> _start() async {
    try {
      final call = await widget.api.createCall(
        phoneNumber: widget.client['phone']?.toString() ?? '',
        direction: 'outgoing',
        borrowerId: widget.client['borrower_id']?.toString(),
        loanId: widget.loan['id']?.toString(),
        deviceId: widget.deviceId,
      );
      if (call['offline'] == true) {
        if (mounted) {
          setState(() {
            stage =
                'Saved offline — Internet access is required for a controlled call.';
            completed = true;
          });
        }
        return;
      }
      callId = call['id']?.toString();
      if (callId == null) {
        throw const LoanHubApiException(
          'LoanHub did not create a call session.',
        );
      }
      if (mounted) setState(() => stage = 'Connecting secure audio…');

      final media = await widget.api.mediaToken(callId!);
      final activeRoom = Room();
      await activeRoom.connect(
        media['server_url'] as String,
        media['token'] as String,
      );
      await activeRoom.localParticipant?.setMicrophoneEnabled(true);
      room = activeRoom;
      if (mounted) {
        setState(
          () => stage =
              'Calling ${widget.client['name'] ?? widget.client['phone']}…',
        );
      }
      await widget.api.dial(callId!);
      timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() => seconds += 1);
      });
      if (mounted) setState(() => stage = 'Business call in progress');
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'Could not start the controlled call. Check your connection and company calling setup.',
        );
      }
    }
  }

  Future<void> _toggleMute() async {
    if (room == null || onHold) return;
    final next = !muted;
    await room?.localParticipant?.setMicrophoneEnabled(!next);
    if (mounted) setState(() => muted = next);
  }

  Future<void> _toggleHold() async {
    if (room == null) return;
    final next = !onHold;
    await room?.localParticipant?.setMicrophoneEnabled(next ? false : !muted);
    if (mounted) {
      setState(() {
        onHold = next;
        stage = next ? 'Client on hold' : 'Business call in progress';
      });
    }
  }

  Future<void> _transfer() async {
    if (callId == null) return;
    final candidates = widget.team
        .where(
          (row) =>
              row['is_current_employee'] != true &&
              row['transfer_target_configured'] == true,
        )
        .toList();
    if (candidates.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('No configured transfer target is available.'),
          ),
        );
      }
      return;
    }
    final selected = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: candidates
              .map(
                (row) => ListTile(
                  leading: const CircleAvatar(child: Icon(Icons.support_agent)),
                  title: Text(row['name']?.toString() ?? 'Employee'),
                  subtitle: Text(row['role']?.toString() ?? ''),
                  onTap: () => Navigator.pop(context, row),
                ),
              )
              .toList(),
        ),
      ),
    );
    if (selected == null) return;
    try {
      await widget.api.transferCall(callId!, selected['staff_id'].toString());
      timer?.cancel();
      await room?.disconnect();
      await room?.dispose();
      room = null;
      if (mounted) {
        setState(() {
          completed = true;
          transferred = true;
          stage = 'Transferred to ${selected['name'] ?? 'colleague'}';
          outcome = 'transferred';
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'Could not transfer the call. Please try again or use another configured colleague.',
        );
      }
    }
  }

  Future<void> _end() async {
    if (ending || transferred) return;
    setState(() => ending = true);
    timer?.cancel();
    try {
      if (callId != null) await widget.api.hangup(callId!);
      await room?.disconnect();
      await room?.dispose();
      room = null;
      if (mounted) setState(() => completed = true);
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Could not end the call from LoanHub. Please try again.',
        );
      }
    } finally {
      if (mounted) setState(() => ending = false);
    }
  }

  Future<void> _save() async {
    if (callId != null) {
      await widget.api.updateCall(callId!, outcome: outcome, notes: notes.text);
    }
    if (mounted) Navigator.pop(context);
  }

  String get timerLabel =>
      '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    if (completed) {
      return Scaffold(
        appBar: AppBar(title: const Text('Call details')),
        body: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            Text(
              widget.client['name']?.toString() ?? 'Client',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
            Text(widget.client['phone']?.toString() ?? ''),
            Text('Duration: $timerLabel'),
            if (transferred) Text(stage),
            const SizedBox(height: 20),
            DropdownButtonFormField<String>(
              initialValue: outcome,
              decoration: const InputDecoration(
                labelText: 'Call outcome',
                border: OutlineInputBorder(),
              ),
              items:
                  const {
                        'payment_made': 'Payment made',
                        'payment_promise': 'Payment promise',
                        'client_unavailable': 'Client unavailable',
                        'wrong_number': 'Wrong number',
                        'dispute': 'Dispute',
                        'refused_to_pay': 'Refused to pay',
                        'callback_requested': 'Callback requested',
                        'information_provided': 'Information provided',
                        'transferred': 'Transferred to colleague',
                        'other': 'Other',
                      }.entries
                      .map(
                        (item) => DropdownMenuItem(
                          value: item.key,
                          child: Text(item.value),
                        ),
                      )
                      .toList(),
              onChanged: (value) => setState(() => outcome = value ?? outcome),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: notes,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Notes',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _save,
              icon: const Icon(Icons.save),
              label: const Text('SAVE CALL DETAILS'),
            ),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: LoanHubColors.brandNavy,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            padding: EdgeInsets.all(
              LoanHubBreakpoints.pagePadding(constraints.maxWidth),
            ),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const SizedBox(height: 24),
                    const CircleAvatar(
                      radius: 46,
                      backgroundColor: LoanHubColors.primary,
                      foregroundColor: Colors.white,
                      child: Icon(Icons.person, size: 42),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      widget.client['name']?.toString() ?? 'Client',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 25,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      widget.client['phone']?.toString() ?? '',
                      style: const TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 22),
                    Text(
                      timerLabel,
                      style: const TextStyle(color: Colors.white, fontSize: 34),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      stage,
                      style: const TextStyle(color: Colors.white70),
                      textAlign: TextAlign.center,
                    ),
                    if (widget.policy['recording_enabled'] == true) ...[
                      const SizedBox(height: 14),
                      const Text(
                        '● Recording policy active',
                        style: TextStyle(color: Colors.redAccent),
                      ),
                    ],
                    if (error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        error!,
                        style: const TextStyle(color: Colors.redAccent),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    const SizedBox(height: 32),
                    Wrap(
                      alignment: WrapAlignment.center,
                      spacing: 18,
                      runSpacing: 14,
                      children: [
                        _CallButton(
                          icon: muted ? Icons.mic_off : Icons.mic,
                          label: muted ? 'Unmute' : 'Mute',
                          onTap: room == null ? null : _toggleMute,
                        ),
                        _CallButton(
                          icon: onHold ? Icons.play_arrow : Icons.pause,
                          label: onHold ? 'Resume' : 'Hold',
                          onTap: room == null ? null : _toggleHold,
                        ),
                        _CallButton(
                          icon: Icons.swap_calls,
                          label: 'Transfer',
                          onTap: room == null ? null : _transfer,
                        ),
                      ],
                    ),
                    const SizedBox(height: 28),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.red.shade700,
                        foregroundColor: Colors.white,
                        minimumSize: const Size(190, 54),
                      ),
                      onPressed: ending ? null : _end,
                      icon: const Icon(Icons.call_end),
                      label: Text(ending ? 'ENDING…' : 'END CALL'),
                    ),
                    const SizedBox(height: 12),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _CallButton extends StatelessWidget {
  const _CallButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final Future<void> Function()? onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton.filledTonal(
          onPressed: onTap == null ? null : () => onTap!(),
          icon: Icon(icon),
          iconSize: 28,
          style: IconButton.styleFrom(
            backgroundColor: Colors.white.withValues(alpha: .14),
            foregroundColor: Colors.white,
            minimumSize: const Size(62, 62),
          ),
        ),
        const SizedBox(height: 5),
        Text(label, style: const TextStyle(color: Colors.white70)),
      ],
    );
  }
}
