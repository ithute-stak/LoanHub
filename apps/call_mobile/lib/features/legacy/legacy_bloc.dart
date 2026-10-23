import 'package:flutter_bloc/flutter_bloc.dart';

sealed class LegacyEvent {
  const LegacyEvent();
}
class LegacyTabSelected extends LegacyEvent {
  final int index;
  const LegacyTabSelected(this.index);
}
class LegacyRecordsReceived extends LegacyEvent {
  final List<Map<String, dynamic>> records;
  const LegacyRecordsReceived(this.records);
}
class LegacyConnectionChanged extends LegacyEvent {
  final bool connected;
  const LegacyConnectionChanged(this.connected);
}
class LegacyReset extends LegacyEvent {
  const LegacyReset();
}
class LegacyState {
  final int tab;
  final List<Map<String, dynamic>> records;
  final bool realtimeConnected;
  const LegacyState({this.tab = 0, this.records = const [], this.realtimeConnected = false});
  LegacyState copyWith({int? tab, List<Map<String, dynamic>>? records, bool? realtimeConnected}) =>
      LegacyState(tab: tab ?? this.tab, records: records ?? this.records,
          realtimeConnected: realtimeConnected ?? this.realtimeConnected);
}
class LegacyBloc extends Bloc<LegacyEvent, LegacyState> {
  LegacyBloc() : super(const LegacyState()) {
    on<LegacyTabSelected>((event, emit) => emit(state.copyWith(tab: event.index)));
    on<LegacyRecordsReceived>((event, emit) =>
        emit(state.copyWith(records: List<Map<String, dynamic>>.unmodifiable(event.records))));
    on<LegacyConnectionChanged>((event, emit) =>
        emit(state.copyWith(realtimeConnected: event.connected)));
    on<LegacyReset>((event, emit) => emit(const LegacyState()));
  }
}
