import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import 'realtime_event.dart';
import 'realtime_repository.dart';

sealed class NotificationBlocEvent {
  const NotificationBlocEvent();
}

final class NotificationRouteRequested extends NotificationBlocEvent {
  const NotificationRouteRequested(this.route);
  final String route;
}

final class NotificationRouteConsumed extends NotificationBlocEvent {
  const NotificationRouteConsumed();
}

final class _NotificationRealtimeArrived extends NotificationBlocEvent {
  const _NotificationRealtimeArrived(this.event);
  final LoanHubRealtimeEvent event;
}

class NotificationBlocState {
  const NotificationBlocState({this.route, this.latestEvent, this.revision = 0});

  final String? route;
  final LoanHubRealtimeEvent? latestEvent;
  final int revision;

  NotificationBlocState copyWith({
    String? route,
    LoanHubRealtimeEvent? latestEvent,
    int? revision,
    bool clearRoute = false,
  }) {
    return NotificationBlocState(
      route: clearRoute ? null : route ?? this.route,
      latestEvent: latestEvent ?? this.latestEvent,
      revision: revision ?? this.revision,
    );
  }
}

class NotificationBloc
    extends Bloc<NotificationBlocEvent, NotificationBlocState> {
  NotificationBloc(this.repository) : super(const NotificationBlocState()) {
    _subscription = repository.events
        .where((event) => event.notification != null)
        .listen((event) => add(_NotificationRealtimeArrived(event)));

    on<_NotificationRealtimeArrived>((event, emit) {
      emit(
        state.copyWith(
          latestEvent: event.event,
          revision: state.revision + 1,
        ),
      );
    });
    on<NotificationRouteRequested>((event, emit) {
      final route = event.route.trim();
      if (route.isEmpty) return;
      emit(state.copyWith(route: route, revision: state.revision + 1));
    });
    on<NotificationRouteConsumed>((event, emit) {
      emit(state.copyWith(clearRoute: true));
    });
  }

  final LoanHubRealtimeRepository repository;
  late final StreamSubscription<LoanHubRealtimeEvent> _subscription;

  @override
  Future<void> close() async {
    await _subscription.cancel();
    return super.close();
  }
}
