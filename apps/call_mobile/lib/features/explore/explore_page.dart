import 'package:flutter/material.dart';

import '../../api/loanhub_api.dart';
import '../../layout/loanhub_responsive.dart';

class ExplorePage extends StatefulWidget {
  const ExplorePage({required this.api, super.key});
  final LoanHubApi api;

  @override
  State<ExplorePage> createState() => _ExplorePageState();
}

class _ExplorePageState extends State<ExplorePage> {
  List<Map<String, dynamic>> posts = const [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) setState(() { loading = true; error = null; });
    try {
      final items = await widget.api.companyChannelPosts();
      if (mounted) setState(() => posts = items);
    } catch (_) {
      if (mounted) setState(() => error = 'Could not load company channels.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final channels = <String, List<Map<String, dynamic>>>{};
    for (final post in posts) {
      final name = post['company_name']?.toString() ?? 'LoanHub company';
      (channels[name] ??= []).add(post);
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: EdgeInsets.all(LoanHubBreakpoints.pagePadding(MediaQuery.sizeOf(context).width)),
        children: [
          Text('Company channels', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 6),
          const Text('Browse verified LoanHub company channels and view their published loan offers and adverts.'),
          const SizedBox(height: 18),
          if (loading && posts.isEmpty) const Center(child: Padding(padding: EdgeInsets.all(36), child: CircularProgressIndicator())),
          if (error != null && posts.isEmpty)
            Center(child: FilledButton.icon(onPressed: _load, icon: const Icon(Icons.refresh), label: const Text('RETRY'))),
          ...channels.entries.map((entry) => _ChannelCard(name: entry.key, posts: entry.value)),
          if (!loading && channels.isEmpty)
            const Card(child: ListTile(
              leading: Icon(Icons.campaign_outlined),
              title: Text('No company offers yet'),
              subtitle: Text('Published LoanHub offers and adverts will appear here.'),
            )),
        ],
      ),
    );
  }
}

class _ChannelCard extends StatelessWidget {
  const _ChannelCard({required this.name, required this.posts});
  final String name;
  final List<Map<String, dynamic>> posts;

  @override
  Widget build(BuildContext context) => Card(
    clipBehavior: Clip.antiAlias,
    child: ExpansionTile(
      leading: CircleAvatar(child: Text(_initials(name))),
      title: Text(name, style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text(posts.length.toString() + ' published offer' + (posts.length == 1 ? '' : 's')),
      children: posts.map((post) => ListTile(
        leading: const Icon(Icons.campaign_outlined),
        title: Text(post['title']?.toString() ?? 'Loan offer'),
        subtitle: Text([
          post['summary']?.toString(),
          post['terms']?.toString(),
        ].whereType<String>().where((value) => value.isNotEmpty).join('\n')),
      )).toList(),
    ),
  );
}

String _initials(String value) {
  final words = value.trim().split(RegExp(r'\s+')).where((item) => item.isNotEmpty).toList();
  if (words.isEmpty) return 'LH';
  if (words.length == 1) return words.first.substring(0, words.first.length > 1 ? 2 : 1).toUpperCase();
  return (words.first[0] + words.last[0]).toUpperCase();
}
