import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import 'realtime_event.dart';
import 'realtime_repository.dart';

sealed class RealtimeBlocEvent {
  const RealtimeBlocEvent();
}

final class RealtimeStarted extends RealtimeBlocEvent {
  const RealtimeStarted();
}

final class RealtimeResumed extends RealtimeBlocEvent {
  const RealtimeResumed();
}

final class RealtimePaused extends RealtimeBlocEvent {
  const RealtimePaused();
}

final class RealtimeStopped extends RealtimeBlocEvent {
  const RealtimeStopped();
}

final class _RealtimeEventArrived extends RealtimeBlocEvent {
  const _RealtimeEventArrived(this.event);
  final LoanHubRealtimeEvent event;
}

final class _RealtimeConnectionChanged extends RealtimeBlocEvent {
  const _RealtimeConnectionChanged(this.status);
  final RealtimeConnectionStatus status;
}

class RealtimeBlocState {
  const RealtimeBlocState({
    this.connection = RealtimeConnectionStatus.stopped,
    this.latestEvent,
    this.revision = 0,
  });

  final RealtimeConnectionStatus connection;
  final LoanHubRealtimeEvent? latestEvent;
  final int revision;

  bool get connected => connection == RealtimeConnectionStatus.connected;

  RealtimeBlocState copyWith({
    RealtimeConnectionStatus? connection,
    LoanHubRealtimeEvent? latestEvent,
    bool clearLatestEvent = false,
    int? revision,
  }) {
    return RealtimeBlocState(
      connection: connection ?? this.connection,
      latestEvent: clearLatestEvent ? null : latestEvent ?? this.latestEvent,
      revision: revision ?? this.revision,
    );
  }
}

class RealtimeBloc extends Bloc<RealtimeBlocEvent, RealtimeBlocState> {
  RealtimeBloc(this.repository) : super(const RealtimeBlocState()) {
    _eventSubscription = repository.events.listen(
      (event) => add(_RealtimeEventArrived(event)),
    );
    _connectionSubscription = repository.connection.listen(
      (status) => add(_RealtimeConnectionChanged(status)),
    );
    on<RealtimeStarted>((event, emit) async => repository.start());
    on<RealtimeResumed>((event, emit) async => repository.resume());
    on<RealtimePaused>((event, emit) async => repository.pause());
    on<RealtimeStopped>((event, emit) async => repository.stop());
    on<_RealtimeEventArrived>((event, emit) {
      emit(
        state.copyWith(
          latestEvent: event.event,
          revision: state.revision + 1,
        ),
      );
    });
    on<_RealtimeConnectionChanged>((event, emit) {
      emit(state.copyWith(connection: event.status));
    });
  }

  final LoanHubRealtimeRepository repository;
  late final StreamSubscription<LoanHubRealtimeEvent> _eventSubscription;
  late final StreamSubscription<RealtimeConnectionStatus>
  _connectionSubscription;

  @override
  Future<void> close() async {
    await _eventSubscription.cancel();
    await _connectionSubscription.cancel();
    await repository.stop();
    return super.close();
  }
}
