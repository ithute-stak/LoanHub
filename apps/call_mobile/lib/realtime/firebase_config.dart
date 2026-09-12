import 'package:firebase_core/firebase_core.dart';

class LoanHubFirebaseConfig {
  LoanHubFirebaseConfig._();

  static const projectId = String.fromEnvironment('LOANHUB_FIREBASE_PROJECT_ID');
  static const appId = String.fromEnvironment('LOANHUB_FIREBASE_APP_ID');
  static const apiKey = String.fromEnvironment('LOANHUB_FIREBASE_API_KEY');
  static const messagingSenderId = String.fromEnvironment(
    'LOANHUB_FIREBASE_MESSAGING_SENDER_ID',
  );

  static bool get configured =>
      projectId.isNotEmpty &&
      appId.isNotEmpty &&
      apiKey.isNotEmpty &&
      messagingSenderId.isNotEmpty;

  static FirebaseOptions? get options {
    if (!configured) return null;
    return const FirebaseOptions(
      apiKey: apiKey,
      appId: appId,
      messagingSenderId: messagingSenderId,
      projectId: projectId,
    );
  }
}
