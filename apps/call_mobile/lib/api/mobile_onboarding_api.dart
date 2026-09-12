import 'dart:convert';
import 'dart:io';

import 'loanhub_api.dart';

class MobileOnboardingApi {
  const MobileOnboardingApi();

  Future<Map<String, dynamic>> registerInterestedClient({
    required String baseUrl,
    required String firstName,
    required String lastName,
    required String phone,
    required String password,
    String? email,
  }) async {
    final root = baseUrl.trim().replaceFirst(RegExp(r'/+$'), '');
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 15);
    try {
      final request = await client.postUrl(
        Uri.parse('$root/api/v1/mobile-onboarding/interested-client'),
      );
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.add(
        utf8.encode(
          jsonEncode({
            'first_name': firstName.trim(),
            'last_name': lastName.trim(),
            'phone': phone.trim(),
            'password': password,
            'email': email?.trim().isEmpty == true ? null : email?.trim(),
          }),
        ),
      );
      final response = await request.close().timeout(
        const Duration(seconds: 30),
      );
      final text = await utf8.decoder.bind(response).join();
      final decoded = text.isEmpty ? <String, dynamic>{} : jsonDecode(text);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final detail = decoded is Map<String, dynamic>
            ? decoded['detail']?.toString()
            : null;
        throw LoanHubApiException(
          detail ?? 'Could not create the LoanHub account.',
          statusCode: response.statusCode,
        );
      }
      return (decoded as Map<String, dynamic>?) ?? <String, dynamic>{};
    } finally {
      client.close(force: true);
    }
  }
}
