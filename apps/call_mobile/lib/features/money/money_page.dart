import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../api/loanhub_api.dart';
import '../../layout/loanhub_responsive.dart';
import '../../realtime/money_bloc.dart';
import '../../theme/loanhub_theme.dart';

class MoneyPage extends StatelessWidget {
  const MoneyPage({required this.api, super.key});

  final LoanHubApi api;

  Future<void> _startTransfer(BuildContext context, String type) async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => MoneyTransferPage(api: api, transferType: type),
      ),
    );
    if (created == true && context.mounted) {
      context.read<MoneyBloc>().add(const MoneyRefreshRequested());
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<MoneyBloc>().state;
    final config = state.configuration;
    final transfers = state.transfers;
    if (state.loading && config.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null && config.isEmpty) {
      return _MoneyInlineError(
        message: state.error!,
        onRetry: () => context.read<MoneyBloc>().add(const MoneyRefreshRequested()),
      );
    }
    final providerReady = config['provider_enabled'] == true;
    return RefreshIndicator(
      onRefresh: () async {
        context.read<MoneyBloc>().add(const MoneyRefreshRequested());
      },
      child: ListView(
        padding: EdgeInsets.all(
          LoanHubBreakpoints.pagePadding(MediaQuery.sizeOf(context).width),
        ),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [LoanHubColors.brandNavy, LoanHubColors.primary],
              ),
              borderRadius: BorderRadius.circular(24),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'LoanHub Money',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 25,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  providerReady
                      ? 'Provider-backed transfers enabled'
                      : 'Transfer-intent mode',
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 18),
                const Row(
                  children: [
                    Icon(Icons.bolt, color: Colors.white70, size: 18),
                    SizedBox(width: 7),
                    Expanded(
                      child: Text(
                        'Realtime payment events update this screen immediately after provider confirmation.',
                        style: TextStyle(color: Colors.white70),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          if (state.latestMoneyEvent?.type == 'MONEY_RECEIVED') ...[
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const CircleAvatar(
                  backgroundColor: LoanHubColors.brandGreen,
                  foregroundColor: Colors.white,
                  child: Icon(Icons.south_west),
                ),
                title: const Text(
                  'Money received',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
                subtitle: Text(
                  '${state.latestMoneyEvent?.data['currency'] ?? 'LSL'} '
                  '${state.latestMoneyEvent?.data['amount'] ?? ''} · provider confirmed',
                ),
              ),
            ),
          ],
          const SizedBox(height: 18),
          Text(
            'Move money',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 1.45,
            children: [
              _MoneyAction(
                icon: Icons.person,
                title: 'C2C',
                subtitle: 'Person to person',
                onTap: () => _startTransfer(context, 'c2c'),
              ),
              _MoneyAction(
                icon: Icons.storefront,
                title: 'C2B',
                subtitle: 'Client to business',
                onTap: () => _startTransfer(context, 'c2b'),
              ),
              _MoneyAction(
                icon: Icons.person_add_alt_1,
                title: 'B2C',
                subtitle: 'Business to client',
                onTap: () => _startTransfer(context, 'b2c'),
              ),
              _MoneyAction(
                icon: Icons.business_center,
                title: 'B2B',
                subtitle: 'Business to business',
                onTap: () => _startTransfer(context, 'b2b'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Recent activity',
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              IconButton(
                onPressed: () =>
                    context.read<MoneyBloc>().add(const MoneyRefreshRequested()),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          if (transfers.isEmpty)
            const Card(
              child: ListTile(
                title: Text('No LoanHub Money transfers yet'),
                subtitle: Text('Your transfer activity will appear here.'),
              ),
            )
          else
            ...transfers.map(
              (row) => Card(
                child: ListTile(
                  leading: CircleAvatar(
                    child: Text(
                      (row['transfer_type'] ?? 'TX').toString().toUpperCase(),
                    ),
                  ),
                  title: Text('M${row['amount']} ${row['currency'] ?? 'LSL'}'),
                  subtitle: Text(
                    '${row['payee_phone'] ?? row['counterparty_reference'] ?? 'LoanHub counterparty'}\n${row['provider'] ?? ''}',
                  ),
                  isThreeLine: true,
                  trailing: _StatusPill(
                    status: row['status']?.toString() ?? 'pending',
                  ),
                ),
              ),
            ),
          const SizedBox(height: 12),
          Text(
            providerReady
                ? 'Transfers remain pending until the configured payment provider confirms settlement.'
                : 'No funds move yet: configure LelefaPayGate before transfer instructions can be dispatched for settlement.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class MoneyTransferPage extends StatefulWidget {
  const MoneyTransferPage({
    required this.api,
    required this.transferType,
    super.key,
  });

  final LoanHubApi api;
  final String transferType;

  @override
  State<MoneyTransferPage> createState() => _MoneyTransferPageState();
}

class _MoneyTransferPageState extends State<MoneyTransferPage> {
  final amount = TextEditingController();
  final phone = TextEditingController();
  final reference = TextEditingController();
  final note = TextEditingController();
  bool sending = false;
  String? error;

  @override
  void dispose() {
    amount.dispose();
    phone.dispose();
    reference.dispose();
    note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final parsedAmount = double.tryParse(amount.text.trim());
    if (parsedAmount == null || parsedAmount <= 0) {
      setState(() => error = 'Enter a valid transfer amount.');
      return;
    }
    if (phone.text.trim().isEmpty && reference.text.trim().isEmpty) {
      setState(
        () => error = 'Enter a phone number or LoanHub counterparty reference.',
      );
      return;
    }
    setState(() {
      sending = true;
      error = null;
    });
    try {
      final result = await widget.api.createMoneyTransfer(
        transferType: widget.transferType,
        amount: amount.text.trim(),
        counterpartyPhone: phone.text.trim().isEmpty ? null : phone.text.trim(),
        counterpartyReference: reference.text.trim().isEmpty
            ? null
            : reference.text.trim(),
        note: note.text.trim().isEmpty ? null : note.text.trim(),
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Transfer instruction created'),
          content: Text(
            'Your transfer instruction has been submitted to LoanHub.\n'
            'Status: ${_displayStatus(result['status'])}\n\n'
            'LoanHub only shows money as received or completed after the configured provider confirms settlement.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('OK'),
            ),
          ],
        ),
      );
      if (mounted) Navigator.pop(context, true);
    } catch (exception) {
      if (mounted) setState(() => error = exception.toString());
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final label = widget.transferType.toUpperCase();
    return Scaffold(
      appBar: AppBar(title: Text('$label transfer')),
      body: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          Text(
            'LoanHub Money · $label',
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          const Text(
            'Create a traceable transfer instruction. Provider confirmation is required before settlement is final.',
          ),
          const SizedBox(height: 20),
          TextField(
            controller: amount,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Amount (LSL)',
              prefixText: 'M ',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: phone,
            keyboardType: TextInputType.phone,
            decoration: const InputDecoration(
              labelText: 'Counterparty phone',
              hintText: '+266 ...',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: reference,
            decoration: const InputDecoration(
              labelText: 'LoanHub / business reference',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: note,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Note / payment reason',
              border: OutlineInputBorder(),
            ),
          ),
          if (error != null) ...[
            const SizedBox(height: 12),
            Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: sending ? null : _submit,
            icon: sending
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.arrow_forward),
            label: Text(sending ? 'CREATING…' : 'CONTINUE'),
          ),
        ],
      ),
    );
  }
}

String _displayStatus(Object? value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty) return 'Pending';
  return text
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty)
      .map((part) => part[0].toUpperCase() + part.substring(1).toLowerCase())
      .join(' ');
}

class _MoneyAction extends StatelessWidget {
  const _MoneyAction({
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
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: LoanHubColors.primary),
              const SizedBox(height: 8),
              Text(
                title,
                style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
              ),
              Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Text(
        status.toUpperCase(),
        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w900),
      ),
    );
  }
}

class _MoneyInlineError extends StatelessWidget {
  const _MoneyInlineError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            minHeight: constraints.hasBoundedHeight &&
                    constraints.maxHeight > 48
                ? constraints.maxHeight - 48
                : 0,
          ),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.cloud_off, size: 48),
                const SizedBox(height: 10),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 12),
                FilledButton.tonalIcon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
