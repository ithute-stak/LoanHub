import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../api/loanhub_api.dart';
import 'realtime_event.dart';
import 'realtime_repository.dart';

sealed class MoneyBlocEvent {
  const MoneyBlocEvent();
}

final class MoneyStarted extends MoneyBlocEvent {
  const MoneyStarted();
}

final class MoneyRefreshRequested extends MoneyBlocEvent {
  const MoneyRefreshRequested();
}

final class _MoneyRealtimeArrived extends MoneyBlocEvent {
  const _MoneyRealtimeArrived(this.event);
  final LoanHubRealtimeEvent event;
}

class MoneyBlocState {
  const MoneyBlocState({
    this.loading = false,
    this.configuration = const <String, dynamic>{},
    this.transfers = const <Map<String, dynamic>>[],
    this.latestMoneyEvent,
    this.revision = 0,
    this.error,
  });

  final bool loading;
  final Map<String, dynamic> configuration;
  final List<Map<String, dynamic>> transfers;
  final LoanHubRealtimeEvent? latestMoneyEvent;
  final int revision;
  final String? error;

  MoneyBlocState copyWith({
    bool? loading,
    Map<String, dynamic>? configuration,
    List<Map<String, dynamic>>? transfers,
    LoanHubRealtimeEvent? latestMoneyEvent,
    int? revision,
    String? error,
    bool clearError = false,
  }) {
    return MoneyBlocState(
      loading: loading ?? this.loading,
      configuration: configuration ?? this.configuration,
      transfers: transfers ?? this.transfers,
      latestMoneyEvent: latestMoneyEvent ?? this.latestMoneyEvent,
      revision: revision ?? this.revision,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class MoneyBloc extends Bloc<MoneyBlocEvent, MoneyBlocState> {
  MoneyBloc(this.api, this.repository) : super(const MoneyBlocState()) {
    _subscription = repository.events.where((event) => event.isMoney).listen(
      (event) => add(_MoneyRealtimeArrived(event)),
    );
    on<MoneyStarted>(_load);
    on<MoneyRefreshRequested>(_load);
    on<_MoneyRealtimeArrived>((event, emit) async {
      emit(
        state.copyWith(
          latestMoneyEvent: event.event,
          revision: state.revision + 1,
        ),
      );
      await _load(event, emit);
    });
  }

  final LoanHubApi api;
  final LoanHubRealtimeRepository repository;
  late final StreamSubscription<LoanHubRealtimeEvent> _subscription;

  Future<void> _load(MoneyBlocEvent event, Emitter<MoneyBlocState> emit) async {
    if (!await api.hasSession()) return;
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final results = await Future.wait<dynamic>([
        api.moneyConfiguration(),
        api.moneyTransfers(),
      ]);
      emit(
        state.copyWith(
          loading: false,
          configuration: results[0] as Map<String, dynamic>,
          transfers: results[1] as List<Map<String, dynamic>>,
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
