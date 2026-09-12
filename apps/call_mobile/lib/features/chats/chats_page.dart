import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../api/loanhub_api.dart';
import '../../realtime/chat_bloc.dart';
import '../../realtime/realtime_repository.dart';
import '../../theme/loanhub_theme.dart';

class ChatsPage extends StatelessWidget {
  const ChatsPage({required this.api, super.key});

  final LoanHubApi api;

  Future<void> _newChat(BuildContext context) async {
    final user = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(builder: (_) => NewChatPage(api: api)),
    );
    if (user == null || !context.mounted) return;
    try {
      final conversation = await api.createConversation(
        participantIds: [user['id'].toString()],
      );
      if (!context.mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ChatThreadPage(api: api, conversation: conversation),
        ),
      );
      if (context.mounted) {
        context.read<ChatBloc>().add(const ChatRefreshRequested());
      }
    } catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<ChatBloc>().state;
    final conversations = state.conversations;
    if (state.loading && conversations.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null && conversations.isEmpty) {
      return _InlineError(
        message: state.error!,
        onRetry: () => context.read<ChatBloc>().add(const ChatRefreshRequested()),
      );
    }
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async {
          context.read<ChatBloc>().add(const ChatRefreshRequested());
        },
        child: conversations.isEmpty
            ? ListView(
                children: const [
                  SizedBox(height: 160),
                  Icon(Icons.forum_outlined, size: 64),
                  SizedBox(height: 14),
                  Center(child: Text('No conversations yet')),
                  SizedBox(height: 6),
                  Center(child: Text('Start a secure LoanHub chat.')),
                ],
              )
            : ListView.separated(
                itemCount: conversations.length,
                separatorBuilder: (_, _) => const Divider(height: 1, indent: 78),
                itemBuilder: (context, index) {
                  final item = conversations[index];
                  final last = item['last_message'] as Map<String, dynamic>?;
                  final unread = (item['unread_count'] as num?)?.toInt() ?? 0;
                  final title = item['title']?.toString() ?? 'LoanHub chat';
                  return ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 7,
                    ),
                    leading: CircleAvatar(
                      radius: 26,
                      backgroundColor: LoanHubColors.primary.withValues(alpha: .14),
                      child: item['is_group'] == true
                          ? const Icon(Icons.groups)
                          : Text(_initials(title)),
                    ),
                    title: Row(
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                        Text(
                          _shortTime(item['last_message_at']?.toString()),
                          style: TextStyle(
                            fontSize: 11,
                            color: unread > 0 ? LoanHubColors.primary : null,
                          ),
                        ),
                      ],
                    ),
                    subtitle: Row(
                      children: [
                        Expanded(
                          child: Text(
                            last?['deleted_at'] != null
                                ? 'Message deleted'
                                : last?['body']?.toString() ??
                                      (last?['message_type'] == 'voice'
                                          ? '🎤 Voice note'
                                          : last?['message_type'] == 'file'
                                          ? '📎 Attachment'
                                          : 'Start chatting'),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (unread > 0) ...[
                          const SizedBox(width: 8),
                          Badge(label: Text(unread > 99 ? '99+' : '$unread')),
                        ],
                      ],
                    ),
                    onTap: () async {
                      await Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ChatThreadPage(
                            api: api,
                            conversation: item,
                          ),
                        ),
                      );
                      if (context.mounted) {
                        context.read<ChatBloc>().add(const ChatRefreshRequested());
                      }
                    },
                  );
                },
              ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _newChat(context),
        tooltip: 'New chat',
        child: const Icon(Icons.chat),
      ),
    );
  }
}

class NewChatPage extends StatefulWidget {
  const NewChatPage({required this.api, super.key});
  final LoanHubApi api;

  @override
  State<NewChatPage> createState() => _NewChatPageState();
}

class _NewChatPageState extends State<NewChatPage> {
  final search = TextEditingController();
  List<Map<String, dynamic>> users = const [];
  bool loading = true;
  Timer? debounce;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    debounce?.cancel();
    search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (mounted) setState(() => loading = true);
    try {
      final rows = await widget.api.chatDirectory(search: search.text);
      if (mounted) setState(() => users = rows);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _searchChanged(String _) {
    debounce?.cancel();
    debounce = Timer(const Duration(milliseconds: 250), _load);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New chat')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: search,
              onChanged: _searchChanged,
              decoration: const InputDecoration(
                hintText: 'Search LoanHub people and businesses',
                prefixIcon: Icon(Icons.search),
              ),
            ),
          ),
          Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    itemCount: users.length,
                    itemBuilder: (context, index) {
                      final user = users[index];
                      final name = user['display_name']?.toString() ?? 'LoanHub user';
                      return ListTile(
                        leading: CircleAvatar(child: Text(_initials(name))),
                        title: Text(name),
                        subtitle: Text(
                          [user['company_name'], user['role'], user['phone']]
                              .where(
                                (value) => value != null && value.toString().isNotEmpty,
                              )
                              .join(' · '),
                        ),
                        trailing: user['is_online'] == true
                            ? const Icon(Icons.circle, size: 10, color: Colors.green)
                            : null,
                        onTap: () => Navigator.pop(context, user),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class ChatThreadPage extends StatefulWidget {
  const ChatThreadPage({
    required this.api,
    required this.conversation,
    super.key,
  });

  final LoanHubApi api;
  final Map<String, dynamic> conversation;

  @override
  State<ChatThreadPage> createState() => _ChatThreadPageState();
}

class _ChatThreadPageState extends State<ChatThreadPage> {
  final composer = TextEditingController();
  final scroll = ScrollController();
  List<Map<String, dynamic>> messages = const [];
  String? myUserId;
  bool sending = false;
  bool partnerTyping = false;
  Timer? typingStopTimer;

  String get conversationId => widget.conversation['id'].toString();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    typingStopTimer?.cancel();
    composer.dispose();
    scroll.dispose();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    try {
      final session = await widget.api.sessionInfo();
      final rows = await widget.api.chatMessages(conversationId);
      await widget.api.markConversationRead(conversationId);
      if (mounted) {
        final changed =
            rows.length != messages.length ||
            (rows.isNotEmpty && messages.isNotEmpty && rows.last['id'] != messages.last['id']);
        setState(() {
          myUserId = session['user_id']?.toString();
          messages = rows;
        });
        if (changed) _scrollToEnd();
      }
    } catch (_) {
      if (!silent && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not refresh this conversation.')),
        );
      }
    }
  }

  void _handleRealtime(ChatBlocState state) {
    final event = state.latestEvent;
    if (event == null) return;
    final eventConversation =
        event.raw['conversation_id']?.toString() ?? event.data['conversation_id']?.toString();
    if (eventConversation != conversationId) return;

    if (event.type == 'CHAT_TYPING') {
      final userId = event.raw['user_id']?.toString();
      if (userId != null && userId != myUserId && mounted) {
        setState(() => partnerTyping = event.raw['is_typing'] == true);
      }
      return;
    }
    if ({
      'CHAT_MESSAGE_CREATED',
      'CHAT_MESSAGE_UPDATED',
      'CHAT_MESSAGE_DELETED',
    }.contains(event.type)) {
      unawaited(_load(silent: true));
    }
  }

  void _composerChanged(String value) {
    final repository = context.read<LoanHubRealtimeRepository>();
    repository.send({
      'type': 'CHAT_TYPING',
      'conversation_id': conversationId,
      'is_typing': value.trim().isNotEmpty,
    });
    typingStopTimer?.cancel();
    if (value.trim().isNotEmpty) {
      typingStopTimer = Timer(const Duration(milliseconds: 1400), () {
        repository.send({
          'type': 'CHAT_TYPING',
          'conversation_id': conversationId,
          'is_typing': false,
        });
      });
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (scroll.hasClients) {
        scroll.animateTo(
          scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = composer.text.trim();
    if (text.isEmpty || sending) return;
    setState(() => sending = true);
    composer.clear();
    _composerChanged('');
    try {
      await widget.api.sendChatMessage(conversationId, text);
      // The server event normally refreshes this instantly. This direct load is
      // a resilience fallback for a socket reconnect occurring at send time.
      await _load(silent: true);
    } catch (error) {
      if (mounted) {
        composer.text = text;
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.conversation['title']?.toString() ?? 'LoanHub chat';
    return BlocListener<ChatBloc, ChatBlocState>(
      listenWhen: (previous, current) => previous.revision != current.revision,
      listener: (_, state) => _handleRealtime(state),
      child: Scaffold(
        appBar: AppBar(
          titleSpacing: 0,
          title: Row(
            children: [
              CircleAvatar(radius: 18, child: Text(_initials(title))),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
                    Text(
                      partnerTyping ? 'typing…' : 'LoanHub secure chat',
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w400),
                    ),
                  ],
                ),
              ),
            ],
          ),
          actions: const [
            IconButton(
              onPressed: null,
              tooltip: 'LoanHub call',
              icon: Icon(Icons.call_outlined),
            ),
          ],
        ),
        body: Column(
          children: [
            Expanded(
              child: Container(
                color: const Color(0xFFEFEAE2),
                child: ListView.builder(
                  controller: scroll,
                  padding: const EdgeInsets.fromLTRB(12, 14, 12, 10),
                  itemCount: messages.length,
                  itemBuilder: (context, index) {
                    final message = messages[index];
                    final sender = message['sender'] as Map<String, dynamic>?;
                    final mine = sender?['id']?.toString() == myUserId;
                    final deleted = message['deleted_at'] != null;
                    final body = deleted
                        ? 'This message was deleted'
                        : message['body']?.toString() ??
                              (message['message_type'] == 'voice'
                                  ? '🎤 Voice note'
                                  : '📎 Attachment');
                    return Align(
                      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                      child: Container(
                        constraints: const BoxConstraints(maxWidth: 330),
                        margin: const EdgeInsets.only(bottom: 6),
                        padding: const EdgeInsets.fromLTRB(12, 8, 10, 6),
                        decoration: BoxDecoration(
                          color: mine
                              ? const Color(0xFFD9FDD3)
                              : Colors.white,
                          borderRadius: BorderRadius.only(
                            topLeft: const Radius.circular(14),
                            topRight: const Radius.circular(14),
                            bottomLeft: Radius.circular(mine ? 14 : 3),
                            bottomRight: Radius.circular(mine ? 3 : 14),
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            if (!mine && widget.conversation['is_group'] == true)
                              Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  sender?['display_name']?.toString() ?? 'LoanHub user',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                            Align(
                              alignment: Alignment.centerLeft,
                              child: Text(
                                body,
                                style: TextStyle(
                                  fontStyle: deleted ? FontStyle.italic : null,
                                ),
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              _shortTime(message['created_at']?.toString()),
                              style: const TextStyle(
                                color: Color(0xFF667781),
                                fontSize: 10,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(
                      child: TextField(
                        controller: composer,
                        minLines: 1,
                        maxLines: 5,
                        textCapitalization: TextCapitalization.sentences,
                        onChanged: _composerChanged,
                        decoration: InputDecoration(
                          filled: true,
                          fillColor: Colors.white,
                          hintText: 'Message',
                          prefixIcon: const Icon(Icons.emoji_emotions_outlined),
                          suffixIcon: IconButton(
                            tooltip: 'Attachments and voice notes',
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'File and voice-note upload is supported by LoanHub chat and will be added to this composer next.',
                                  ),
                                ),
                              );
                            },
                            icon: const Icon(Icons.attach_file),
                          ),
                        ),
                        onSubmitted: (_) => _send(),
                      ),
                    ),
                    const SizedBox(width: 7),
                    FloatingActionButton.small(
                      heroTag: null,
                      onPressed: sending ? null : _send,
                      child: Icon(sending ? Icons.hourglass_top : Icons.send),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
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

String _shortTime(String? value) {
  if (value == null || value.isEmpty) return '';
  try {
    final date = DateTime.parse(value).toLocal();
    final now = DateTime.now();
    if (date.year == now.year &&
        date.month == now.month &&
        date.day == now.day) {
      final hour = date.hour.toString().padLeft(2, '0');
      final minute = date.minute.toString().padLeft(2, '0');
      return '$hour:$minute';
    }
    return '${date.day}/${date.month}';
  } catch (_) {
    return '';
  }
}
