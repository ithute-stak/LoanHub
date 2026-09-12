import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../api/loanhub_api.dart';
import 'realtime_event.dart';
import 'realtime_repository.dart';

sealed class ChatBlocEvent {
  const ChatBlocEvent();
}

final class ChatStarted extends ChatBlocEvent {
  const ChatStarted();
}

final class ChatRefreshRequested extends ChatBlocEvent {
  const ChatRefreshRequested();
}

final class _ChatRealtimeArrived extends ChatBlocEvent {
  const _ChatRealtimeArrived(this.event);
  final LoanHubRealtimeEvent event;
}

class ChatBlocState {
  const ChatBlocState({
    this.loading = false,
    this.conversations = const <Map<String, dynamic>>[],
    this.unreadCount = 0,
    this.latestEvent,
    this.revision = 0,
    this.error,
  });

  final bool loading;
  final List<Map<String, dynamic>> conversations;
  final int unreadCount;
  final LoanHubRealtimeEvent? latestEvent;
  final int revision;
  final String? error;

  ChatBlocState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? conversations,
    int? unreadCount,
    LoanHubRealtimeEvent? latestEvent,
    int? revision,
    String? error,
    bool clearError = false,
  }) {
    return ChatBlocState(
      loading: loading ?? this.loading,
      conversations: conversations ?? this.conversations,
      unreadCount: unreadCount ?? this.unreadCount,
      latestEvent: latestEvent ?? this.latestEvent,
      revision: revision ?? this.revision,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class ChatBloc extends Bloc<ChatBlocEvent, ChatBlocState> {
  ChatBloc(this.api, this.repository) : super(const ChatBlocState()) {
    _subscription = repository.events.where((event) => event.isChat).listen(
      (event) => add(_ChatRealtimeArrived(event)),
    );
    on<ChatStarted>(_load);
    on<ChatRefreshRequested>(_load);
    on<_ChatRealtimeArrived>((event, emit) async {
      emit(
        state.copyWith(
          latestEvent: event.event,
          revision: state.revision + 1,
        ),
      );
      // Typing is ephemeral and should not cause an API reload. Persisted chat
      // mutations immediately rehydrate the encrypted server state.
      if (event.event.type == 'CHAT_TYPING') return;
      await _load(event, emit);
    });
  }

  final LoanHubApi api;
  final LoanHubRealtimeRepository repository;
  late final StreamSubscription<LoanHubRealtimeEvent> _subscription;

  Future<void> _load(ChatBlocEvent event, Emitter<ChatBlocState> emit) async {
    if (!await api.hasSession()) return;
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final results = await Future.wait<dynamic>([
        api.chatConversations(),
        api.chatUnreadCount(),
      ]);
      emit(
        state.copyWith(
          loading: false,
          conversations: results[0] as List<Map<String, dynamic>>,
          unreadCount: results[1] as int,
          revision: state.revision + 1,
          clearError: true,
        ),
      );
    } catch (error) {
      emit(state.copyWith(loading: false, error: error.toString()));
    }
  }

  @override
  Future<void> close() async {
    await _subscription.cancel();
    return super.close();
  }
}
