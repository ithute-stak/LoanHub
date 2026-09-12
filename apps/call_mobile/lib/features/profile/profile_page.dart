import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../api/loanhub_api.dart';
import '../../layout/loanhub_responsive.dart';
import '../../realtime/realtime_repository.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({
    required this.api,
    required this.onSignedOut,
    super.key,
  });

  final LoanHubApi api;
  final Future<void> Function() onSignedOut;

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  Map<String, dynamic>? session;

  @override
  void initState() {
    super.initState();
    widget.api.sessionInfo().then((value) {
      if (mounted) setState(() => session = value);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (session == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final name = session?['display_name']?.toString() ?? 'LoanHub user';
    return ListView(
      padding: EdgeInsets.all(
        LoanHubBreakpoints.pagePadding(MediaQuery.sizeOf(context).width),
      ),
      children: [
        Center(
          child: CircleAvatar(
            radius: 48,
            child: Text(
              _initials(name),
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          name,
          textAlign: TextAlign.center,
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
        ),
        Text(
          session?['role']?.toString().replaceAll('_', ' ') ?? '',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 22),
        Card(
          child: Column(
            children: [
              ListTile(
                leading: const Icon(Icons.business_outlined),
                title: const Text('Active company'),
                subtitle: const Text(
                  'Your authorised LoanHub business workspace',
                ),
              ),
              const Divider(height: 1),
              const ListTile(
                leading: Icon(Icons.notifications_active_outlined),
                title: Text('Realtime notifications'),
                subtitle: Text(
                  'Messages and provider-confirmed incoming money can ring this device in the background.',
                ),
              ),
              const Divider(height: 1),
              const ListTile(
                leading: Icon(Icons.lock_outline),
                title: Text('Privacy & security'),
                subtitle: Text(
                  'LoanHub permissions, secure chats and transaction controls',
                ),
              ),
              const Divider(height: 1),
              const ListTile(
                leading: Icon(Icons.help_outline),
                title: Text('Help & support'),
                subtitle: Text('Start a LoanHub support conversation'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        OutlinedButton.icon(
          onPressed: () async {
            try {
              await context.read<LoanHubRealtimeRepository>().revokePushDevice();
            } catch (_) {
              // If the device is offline, a later account registration also
              // revokes this installation from the old account server-side.
            }
            await widget.api.logout();
            await widget.onSignedOut();
          },
          icon: const Icon(Icons.logout),
          label: const Text('SIGN OUT'),
        ),
      ],
    );
  }
}

String _initials(String value) {
  final words = value
      .trim()
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .toList();
  if (words.isEmpty) return 'LH';
  if (words.length == 1) {
    return words.first
        .substring(0, words.first.length >= 2 ? 2 : 1)
        .toUpperCase();
  }
  return '${words.first[0]}${words.last[0]}'.toUpperCase();
}
