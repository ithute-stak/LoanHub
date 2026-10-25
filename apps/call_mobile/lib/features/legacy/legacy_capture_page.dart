import 'dart:io';
import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import 'legacy_bloc.dart';
import '../../api/loanhub_api.dart';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

class LegacyCapturePage extends StatefulWidget {
  const LegacyCapturePage({required this.api, super.key});
  final LoanHubApi api;
  @override
  State<LegacyCapturePage> createState() => _LegacyCapturePageState();
}

class _LegacyCapturePageState extends State<LegacyCapturePage> {
  final apiUrl = TextEditingController(
    text: const String.fromEnvironment(
      'LOANHUB_API_URL',
      defaultValue: 'https://api.loanhub.co.ls/api/v1',
    ),
  );
  final token = TextEditingController();
  final companyId = TextEditingController();
  List<Map<String, dynamic>> memberships = [];
  Map<String, String> companyNames = {};
  final name = TextEditingController();
  final employer = TextEditingController();
  final account = TextEditingController();
  final amount = TextEditingController();
  final search = TextEditingController();
  String groupFilter = 'all';
  List<Map<String, dynamic>> groups = [];
  List<String> employerOptions = [];
  bool addingEmployer = false;
  List<Map<String, dynamic>> rows = [];
  String? selectedGroup;
  String? error;
  bool loading = false;
  bool configured = false;
  WebSocket? realtimeSocket;
  Timer? realtimeRetry;
  bool shuttingDown = false;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    token.text =
        await widget.api.storage.read(key: 'loanhub_access_token') ?? '';
    companyId.text =
        await widget.api.storage.read(key: 'loanhub_company_id') ?? '';
    apiUrl.text = '${await widget.api.baseUrl()}/api/v1';
    if (token.text.isNotEmpty) {
      await _resolveCompany();
    }
  }

  Future<Map<String, String>> _authHeaders() async {
    final accessToken = await widget.api.storage.read(
      key: 'loanhub_access_token',
    );
    if (accessToken == null || accessToken.isEmpty) {
      throw StateError(
        'Your LoanHub session is unavailable. Sign in through the main app.',
      );
    }
    return <String, String>{
      'Authorization': 'Bearer $accessToken',
      'X-Company-ID': companyId.text.trim(),
      'Content-Type': 'application/json',
    };
  }

  Future<http.Response> _request(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = Uri.parse('${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}$path');
    final headers = await _authHeaders();
    return body == null
        ? http.get(uri, headers: headers)
        : http.post(uri, headers: headers, body: jsonEncode(body));
  }

  Future<void> _resolveCompany() async {
    try {
      final response = await http.get(
        Uri.parse('${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}/auth/me'),
        headers: await _authHeaders(),
      );
      if (response.statusCode != 200) {
        throw Exception('Your session expired. Sign in again through LoanHub.');
      }
      final profile = jsonDecode(response.body) as Map<String, dynamic>;
      memberships = ((profile['memberships'] as List?) ?? [])
          .whereType<Map<String, dynamic>>()
          .where((item) => item['is_active'] == true)
          .toList();
      if (memberships.isEmpty) {
        throw Exception(
          'Your account has no active LoanHub company membership.',
        );
      }
      final activeCompany = (await widget.api.sessionInfo())['company_id']
          ?.toString();
      if (activeCompany == null ||
          activeCompany.isEmpty ||
          !memberships.any(
            (m) => m['company_id'].toString() == activeCompany,
          )) {
        throw StateError(
          'Select an authorised company in the main LoanHub app before opening Legacy CSV.',
        );
      }
      companyId.text = activeCompany;
      final companyResponse = await http.get(
        Uri.parse(
          '${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}/companies/?limit=500',
        ),
        headers: {'Authorization': 'Bearer ${token.text.trim()}'},
      );
      if (companyResponse.statusCode == 200) {
        final companies = (jsonDecode(companyResponse.body) as List)
            .cast<Map<String, dynamic>>();
        companyNames = {
          for (final item in companies)
            item['id'].toString(): item['name'].toString(),
        };
      }
      await _connect();
    } catch (e) {
      if (mounted)
        setState(() {
          configured = false;
          error = e.toString();
        });
    }
  }

  Future<void> _connect() async {
    if (!mounted) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final answers = await Future.wait([
        _request('/legacy-bank-deductions/work-groups'),
        _request('/legacy-bank-deductions/'),
        _request('/legacy-bank-deductions/employers'),
      ]);
      if (answers.any((r) => r.statusCode >= 400))
        throw Exception(
          'Connection or permission denied. Check your company and sign-in.',
        );
      groups = (jsonDecode(answers[0].body) as List)
          .cast<Map<String, dynamic>>();
      if (answers[2].statusCode == 200) {
        employerOptions = (jsonDecode(answers[2].body) as List)
            .map((entry) => entry.toString())
            .toList();
      }
      rows = (jsonDecode(answers[1].body) as List).cast<Map<String, dynamic>>();
      // Session ownership remains with the parent LoanHub application.
      configured = true;
      if (mounted) context.read<LegacyBloc>().add(LegacyRecordsReceived(rows));
      if (realtimeSocket == null) unawaited(_connectRealtime());
    } catch (e) {
      error = e.toString();
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _restoreRecord() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await _request('/legacy-bank-deductions/deleted');
      if (response.statusCode == 403) {
        throw Exception('Only company management can restore records.');
      }
      if (response.statusCode != 200)
        throw Exception('Could not load removed records.');
      final deleted = (jsonDecode(response.body) as List)
          .cast<Map<String, dynamic>>();
      if (!mounted) return;
      final selected = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Restore a deleted record'),
          content: SizedBox(
            width: 480,
            child: deleted.isEmpty
                ? const Text('No deleted records available.')
                : ListView(
                    shrinkWrap: true,
                    children: deleted
                        .map(
                          (row) => ListTile(
                            title: Text(row['client_name'].toString()),
                            subtitle: Text(
                              'Account ••••${row['account_last4']} · M ${row['amount']}',
                            ),
                            trailing: const Icon(Icons.restore),
                            onTap: () =>
                                Navigator.pop(ctx, row['id'].toString()),
                          ),
                        )
                        .toList(),
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Close'),
            ),
          ],
        ),
      );
      if (selected == null) return;
      final result = await _request(
        '/legacy-bank-deductions/$selected/restore',
        body: {},
      );
      if (result.statusCode != 200)
        throw Exception('Unable to restore record.');
      final refreshed = await _request('/legacy-bank-deductions/');
      if (refreshed.statusCode != 200)
        throw Exception('Restored but table refresh failed.');
      rows = (jsonDecode(refreshed.body) as List).cast<Map<String, dynamic>>();
      if (mounted) context.read<LegacyBloc>().add(LegacyRecordsReceived(rows));
    } catch (e) {
      error = e.toString();
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _importCsv() async {
    if (selectedGroup == null) {
      setState(() => error = 'Select CIVIL, FORCE or S/E before importing.');
      return;
    }
    final item = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['csv', 'xlsx'],
    );
    if (item == null) return;
    final size = await item.length();
    if (size == null || size > 2000000) {
      setState(() => error = 'CSV/XLSX file must be no larger than 2 MB.');
      return;
    }
    final bytes = await item.readAsBytes();
    if (bytes.isEmpty) {
      setState(() => error = 'Unable to read the selected file.');
      return;
    }
    Future<Map<String, dynamic>> submit(bool preview) async {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse(
          '${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}/legacy-bank-deductions/import-csv?preview=$preview&work_group_id=${Uri.encodeQueryComponent(selectedGroup!)}',
        ),
      );
      request.headers.addAll(await _authHeaders());
      request.files.add(
        http.MultipartFile.fromBytes('file', bytes, filename: item.name),
      );
      final response = await http.Response.fromStream(await request.send());
      final decoded = jsonDecode(response.body);
      if (response.statusCode >= 400) {
        throw Exception('CSV validation failed: ${response.body}');
      }
      return (decoded as Map).cast<String, dynamic>();
    }

    setState(() {
      loading = true;
      error = null;
    });
    try {
      final preview = await submit(true);
      if (!mounted) return;
      final issues = (preview['issues'] as List? ?? []);
      final summary =
          'Ready: ${preview['valid']}  •  Rejected: ${preview['rejected']}';
      final details = issues
          .take(8)
          .map((issue) => 'Row ${issue['row']}: ${issue['reason']}')
          .join('\n');
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Review CSV import'),
          content: SingleChildScrollView(
            child: Text(
              '$summary\n\n${details.isEmpty ? "All rows passed validation." : details}',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed:
                  (preview['rejected'] as num) > 0 ||
                      (preview['valid'] as num) == 0
                  ? null
                  : () => Navigator.pop(ctx, true),
              child: const Text('Import valid rows'),
            ),
          ],
        ),
      );
      if (confirmed == true) {
        final result = await submit(false);
        final listing = await _request('/legacy-bank-deductions/');
        if (listing.statusCode != 200)
          throw Exception('Import saved, but refresh failed.');
        rows = (jsonDecode(listing.body) as List).cast<Map<String, dynamic>>();
        if (mounted)
          context.read<LegacyBloc>().add(LegacyRecordsReceived(rows));
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Imported ${result['saved']} legacy deductions.'),
            ),
          );
        }
      }
    } catch (e) {
      error = e.toString();
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _exportZip({bool combined = false}) async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await _request(
        combined
            ? '/legacy-bank-deductions/combined-export.zip'
            : '/legacy-bank-deductions/export.zip',
      );
      if (response.statusCode != 200) {
        throw Exception('Export unavailable. Check records and permissions.');
      }
      final directory = await getTemporaryDirectory();
      final archive = File(
        '${directory.path}/loanhub-${combined ? 'combined' : 'legacy'}-bank-submissions.zip',
      );
      await archive.writeAsBytes(response.bodyBytes, flush: true);
      await SharePlus.instance.share(
        ShareParams(
          files: [XFile(archive.path, mimeType: 'application/zip')],
          subject: 'LoanHub legacy bank deductions',
          text: 'Confidential bank submission. Share only with an authorised recipient.',
        ),
      );
    } catch (e) {
      error = e.toString();
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _deleteAllLegacy() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final preview = await _request(
        '/legacy-bank-deductions/bulk-delete/preview',
      );
      if (preview.statusCode == 403)
        throw Exception(
          'Only company management can delete all legacy records.',
        );
      if (preview.statusCode != 200)
        throw Exception('Unable to check deletion permissions.');
      final count =
          (jsonDecode(preview.body) as Map<String, dynamic>)['count'] as int;
      if (count == 0) {
        if (mounted)
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('No active legacy records to delete.'),
            ),
          );
        return;
      }
      if (!mounted) return;
      final confirmation = TextEditingController();
      bool confirmed = false;
      try {
        confirmed =
            await showDialog<bool>(
              context: context,
              builder: (dialogContext) => StatefulBuilder(
                builder: (ctx, refresh) => AlertDialog(
                  title: const Text('Delete ALL legacy deductions?'),
                  content: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          'This will remove $count historical deductions for this company from the active register and bank exports. Current loans and payments are not affected. Deleted records remain recoverable.',
                        ),
                        const SizedBox(height: 14),
                        TextField(
                          controller: confirmation,
                          onChanged: (_) => refresh(() {}),
                          decoration: const InputDecoration(
                            labelText: 'Type DELETE LEGACY RECORDS',
                          ),
                        ),
                      ],
                    ),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx, false),
                      child: const Text('Cancel'),
                    ),
                    FilledButton(
                      onPressed: confirmation.text == 'DELETE LEGACY RECORDS'
                          ? () => Navigator.pop(ctx, true)
                          : null,
                      child: const Text('Remove all legacy records'),
                    ),
                  ],
                ),
              ),
            ) ??
            false;
      } finally {
        confirmation.dispose();
      }
      if (!confirmed) return;
      final result = await _request(
        '/legacy-bank-deductions/bulk-delete',
        body: {
          'confirmation': 'DELETE LEGACY RECORDS',
          'expected_count': count,
        },
      );
      if (result.statusCode != 200)
        throw Exception('Bulk deletion failed: ${result.body}');
      await _connect();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '$count legacy deductions removed. Current loans are unchanged.',
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _save() async {
    if (selectedGroup == null ||
        name.text.trim().isEmpty ||
        employer.text.trim().isEmpty ||
        account.text.trim().isEmpty ||
        amount.text.trim().isEmpty) {
      setState(() => error = 'Complete all fields before saving.');
      return;
    }
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await _request(
        '/legacy-bank-deductions/',
        body: {
          'work_group_id': selectedGroup,
          'client_name': name.text.trim(),
          'employer': employer.text.trim(),
          'account_number': account.text.trim(),
          'amount': amount.text.trim(),
        },
      );
      if (response.statusCode != 201)
        throw Exception('Could not save record: ${response.body}');
      name.clear();
      employer.clear();
      account.clear();
      amount.clear();
      final listing = await _request('/legacy-bank-deductions/');
      if (listing.statusCode != 200)
        throw Exception('Saved, but refresh failed');
      rows = (jsonDecode(listing.body) as List).cast<Map<String, dynamic>>();
      if (mounted) context.read<LegacyBloc>().add(LegacyRecordsReceived(rows));
    } catch (e) {
      error = e.toString();
    }
    if (mounted) setState(() => loading = false);
  }

  List<Map<String, dynamic>> get visibleRows => rows.where((row) {
    final query = search.text.trim().toLowerCase();
    final matchesSearch =
        query.isEmpty ||
        [
          'client_name',
          'employer',
          'masked_account',
          'branch_code',
          'work_group',
        ].any(
          (key) => (row[key] ?? '').toString().toLowerCase().contains(query),
        );
    final matchesGroup =
        groupFilter == 'all' || row['work_group_id']?.toString() == groupFilter;
    return matchesSearch && matchesGroup;
  }).toList();

  Future<void> _modifyRecord(
    Map<String, dynamic> row, {
    required bool remove,
  }) async {
    final currentName = TextEditingController(
      text: row['client_name']?.toString() ?? '',
    );
    final currentEmployer = TextEditingController(
      text: row['employer']?.toString() ?? '',
    );
    final currentAmount = TextEditingController(
      text: row['amount']?.toString() ?? '',
    );
    var selected = row['work_group_id']?.toString();
    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => StatefulBuilder(
          builder: (ctx, refresh) => AlertDialog(
            title: Text(
              remove ? 'Remove legacy record?' : 'Edit legacy record',
            ),
            content: remove
                ? Text(
                    'Remove the entry for ${row['client_name']}? It will no longer be included in future CSV exports. This action cannot be undone.',
                  )
                : SizedBox(
                    width: 400,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        DropdownButtonFormField<String>(
                          initialValue: selected,
                          decoration: const InputDecoration(
                            labelText: 'Work group',
                          ),
                          items: groups
                              .map(
                                (g) => DropdownMenuItem(
                                  value: g['id'].toString(),
                                  child: Text(g['name'].toString()),
                                ),
                              )
                              .toList(),
                          onChanged: (v) => refresh(() => selected = v),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: currentName,
                          decoration: const InputDecoration(
                            labelText: 'Client name',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: currentEmployer,
                          decoration: const InputDecoration(
                            labelText: 'Employer',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: currentAmount,
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          decoration: const InputDecoration(
                            labelText: 'Deduction amount (LSL)',
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Bank account number cannot be changed here. Remove and re-enter the record to change account details.',
                        ),
                      ],
                    ),
                  ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: Text(remove ? 'Remove' : 'Save changes'),
              ),
            ],
          ),
        ),
      );
      if (confirmed != true) return;
      if (!remove &&
          (selected == null ||
              currentName.text.trim().isEmpty ||
              currentEmployer.text.trim().isEmpty ||
              currentAmount.text.trim().isEmpty)) {
        setState(() => error = 'Complete all edit fields.');
        return;
      }
      setState(() {
        loading = true;
        error = null;
      });
      final uri = Uri.parse(
        '${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}/legacy-bank-deductions/${row['id']}',
      );
      final headers = await _authHeaders();
      final response = remove
          ? await http.delete(uri, headers: headers)
          : await http.patch(
              uri,
              headers: headers,
              body: jsonEncode({
                'work_group_id': selected,
                'client_name': currentName.text.trim(),
                'employer': currentEmployer.text.trim(),
                'amount': currentAmount.text.trim(),
              }),
            );
      if (response.statusCode != (remove ? 204 : 200)) {
        throw Exception('Could not update record: ${response.statusCode}');
      }
      final listing = await _request('/legacy-bank-deductions/');
      if (listing.statusCode != 200)
        throw Exception('Update saved, but refresh failed');
      rows = (jsonDecode(listing.body) as List).cast<Map<String, dynamic>>();
      if (mounted) context.read<LegacyBloc>().add(LegacyRecordsReceived(rows));
    } catch (e) {
      error = e.toString();
    } finally {
      currentName.dispose();
      currentEmployer.dispose();
      currentAmount.dispose();
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _connectRealtime() async {
    if (!mounted || !configured || shuttingDown) return;
    realtimeRetry?.cancel();
    await realtimeSocket?.close();
    try {
      final base = Uri.parse(apiUrl.text.trim());
      final uri = base.replace(
        scheme: base.scheme == 'https' ? 'wss' : 'ws',
        path: '/ws',
        queryParameters: {'company_id': companyId.text.trim()},
      );
      final accessToken = await widget.api.storage.read(
        key: 'loanhub_access_token',
      );
      if (accessToken == null || accessToken.isEmpty) return;
      final socket = await WebSocket.connect(
        uri.toString(),
        protocols: ['loanhub.v1', 'loanhub.jwt.$accessToken'],
      );
      if (!mounted || !configured || shuttingDown) {
        await socket.close();
        return;
      }
      realtimeSocket = socket;
      context.read<LegacyBloc>().add(const LegacyConnectionChanged(true));
      socket.listen(
        (message) {
          try {
            final payload = jsonDecode(message.toString());
            if (payload is Map &&
                payload['type'] == 'DB_EVENT' &&
                payload['company_id']?.toString() == companyId.text.trim()) {
              unawaited(_connect());
            }
          } catch (_) {}
        },
        onDone: _retryRealtime,
        onError: (_) => _retryRealtime(),
        cancelOnError: true,
      );
    } catch (_) {
      _retryRealtime();
    }
  }

  void _retryRealtime() {
    if (!mounted || !configured || shuttingDown) return;
    context.read<LegacyBloc>().add(const LegacyConnectionChanged(false));
    realtimeRetry?.cancel();
    realtimeRetry = Timer(
      const Duration(seconds: 8),
      () => unawaited(_connectRealtime()),
    );
  }

  Widget field(
    String label,
    TextEditingController controller, {
    bool numeric = false,
    bool money = false,
  }) => TextField(
    controller: controller,
    keyboardType: numeric
        ? TextInputType.number
        : money
        ? const TextInputType.numberWithOptions(decimal: true)
        : TextInputType.text,
    inputFormatters: numeric
        ? [FilteringTextInputFormatter.digitsOnly]
        : money
        ? [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}$'))]
        : null,
    decoration: InputDecoration(
      labelText: label,
      filled: true,
      fillColor: Colors.white,
    ),
    maxLength: numeric ? 20 : null,
  );

  Widget _capture() => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        'New deduction',
        style: Theme.of(context).textTheme.headlineSmall
            ?.copyWith(fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 8),
      const Text(
        'Account details stay encrypted in LoanHub. Branch code is automatically resolved from configured bank rules.',
      ),
      const SizedBox(height: 14),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: selectedGroup,
                decoration: const InputDecoration(labelText: 'Work group'),
                items: groups
                    .map(
                      (g) => DropdownMenuItem<String>(
                        value: g['id'].toString(),
                        child: Text(
                          g['name'].toString(),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    )
                    .toList(),
                onChanged: loading
                    ? null
                    : (v) => setState(() => selectedGroup = v),
              ),
              const SizedBox(height: 12),
              field('Client name', name),
              const SizedBox(height: 12),
              Autocomplete<String>(
                initialValue: TextEditingValue(text: employer.text),
                optionsBuilder: (value) {
                  final query = value.text.trim().toLowerCase();
                  if (query.isEmpty) return employerOptions;
                  final matches = employerOptions
                      .where((entry) => entry.toLowerCase().contains(query))
                      .toList();
                  if (!employerOptions.any(
                    (entry) => entry.trim().toLowerCase() == query,
                  )) {
                    matches.add('＋ Add new employer: ${value.text.trim()}');
                  }
                  return matches;
                },
                displayStringForOption: (entry) =>
                    entry.startsWith('＋ Add new employer: ')
                    ? entry.substring('＋ Add new employer: '.length)
                    : entry,
                onSelected: (entry) => setState(() {
                  employer.text = entry.startsWith('＋ Add new employer: ')
                      ? entry.substring('＋ Add new employer: '.length)
                      : entry;
                  addingEmployer = false;
                }),
                fieldViewBuilder:
                    (ctx, controller, focusNode, onFieldSubmitted) {
                      return TextField(
                        controller: controller,
                        focusNode: focusNode,
                        textCapitalization: TextCapitalization.words,
                        decoration: InputDecoration(
                          labelText: 'Employer',
                          hintText: 'Search or type a new employer',
                          prefixIcon: const Icon(Icons.search),
                          suffixIcon: const Icon(Icons.business_outlined),
                        ),
                        onChanged: (value) {
                          employer.text = value;
                          addingEmployer = !employerOptions.any(
                            (entry) =>
                                entry.toLowerCase() ==
                                value.trim().toLowerCase(),
                          );
                        },
                      );
                    },
                optionsViewBuilder: (ctx, onSelected, options) => Align(
                  alignment: Alignment.topLeft,
                  child: Material(
                    elevation: 4,
                    borderRadius: BorderRadius.circular(12),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 240),
                      child: ListView(
                        padding: EdgeInsets.zero,
                        shrinkWrap: true,
                        children: options
                            .map(
                              (entry) => ListTile(
                                dense: true,
                                title: Text(entry),
                                onTap: () => onSelected(entry),
                              ),
                            )
                            .toList(),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              field('Account number', account, numeric: true),
              const SizedBox(height: 12),
              field('Amount (LSL)', amount, money: true),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: loading ? null : _save,
                icon: const Icon(Icons.add_circle_outline),
                label: const Text('Save deduction'),
              ),
            ],
          ),
        ),
      ),
    ],
  );

  Widget _records() => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        'Saved deductions',
        style: Theme.of(context).textTheme.headlineSmall
            ?.copyWith(fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: search,
        onChanged: (_) => setState(() {}),
        decoration: const InputDecoration(
          prefixIcon: Icon(Icons.search),
          labelText: 'Search client, employer, account',
        ),
      ),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(
        isExpanded: true,
        initialValue: 'all',
        decoration: const InputDecoration(labelText: 'Work group'),
        items: [
          const DropdownMenuItem(value: 'all', child: Text('All groups')),
          ...groups.map(
            (g) => DropdownMenuItem(
              value: g['id'].toString(),
              child: Text(g['name'].toString()),
            ),
          ),
        ],
        onChanged: (v) => setState(() => groupFilter = v ?? 'all'),
      ),
      const SizedBox(height: 12),
      Text(
        '${visibleRows.length} of ${rows.length} records',
        style: Theme.of(context).textTheme.labelLarge,
      ),
      const SizedBox(height: 8),
      LayoutBuilder(
        builder: (ctx, constraints) {
          if (constraints.maxWidth < 620) {
            return Column(
              children: [
                ...visibleRows.map(
                  (row) => Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            row['client_name'].toString(),
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 5),
                          Text(
                            '${row['work_group']} · ${row['employer'] ?? 'Unassigned'} · ${row['masked_account']}',
                          ),
                          Text(
                            'Branch: ${row['branch_code']}    M ${row['amount']}',
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: Wrap(
                              spacing: 4,
                              children: [
                                IconButton(
                                  tooltip: 'Edit',
                                  icon: const Icon(Icons.edit_outlined),
                                  onPressed: loading
                                      ? null
                                      : () => _modifyRecord(row, remove: false),
                                ),
                                IconButton(
                                  tooltip: 'Remove',
                                  icon: const Icon(Icons.delete_outline),
                                  onPressed: loading
                                      ? null
                                      : () => _modifyRecord(row, remove: true),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            );
          }
          return SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              columns: const [
                DataColumn(label: Text('Group')),
                DataColumn(label: Text('Client')),
                DataColumn(label: Text('Employer')),
                DataColumn(label: Text('Account')),
                DataColumn(label: Text('Branch')),
                DataColumn(label: Text('Amount')),
                DataColumn(label: Text('Edit')),
              ],
              rows: visibleRows
                  .map(
                    (row) => DataRow(
                      cells: [
                        DataCell(Text(row['work_group'].toString())),
                        DataCell(Text(row['client_name'].toString())),
                        DataCell(
                          Text((row['employer'] ?? 'Unassigned').toString()),
                        ),
                        DataCell(Text(row['masked_account'].toString())),
                        DataCell(Text(row['branch_code'].toString())),
                        DataCell(Text(row['amount'].toString())),
                        DataCell(
                          IconButton(
                            icon: const Icon(Icons.edit),
                            onPressed: () => _modifyRecord(row, remove: false),
                          ),
                        ),
                      ],
                    ),
                  )
                  .toList(),
            ),
          );
        },
      ),
    ],
  );

  Widget _tools() => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        'Import & export',
        style: Theme.of(context).textTheme.headlineSmall
            ?.copyWith(fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 8),
      const Text(
        'Bulk CSV/XLSX import: Client name, Account number, Amount, Employer. Choose a work group once.',
      ),
      const SizedBox(height: 16),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue: selectedGroup,
                decoration: const InputDecoration(
                  labelText: 'Work group for imported rows',
                ),
                items: groups
                    .map(
                      (g) => DropdownMenuItem<String>(
                        value: g['id'].toString(),
                        child: Text(
                          g['name'].toString(),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (v) => setState(() => selectedGroup = v),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: loading || selectedGroup == null ? null : _importCsv,
                icon: const Icon(Icons.upload_file),
                label: const Text('Import CSV / Excel'),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: loading || rows.isEmpty ? null : _exportZip,
                icon: const Icon(Icons.archive_outlined),
                label: const Text('Export bank ZIP'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: loading ? null : () => _exportZip(combined: true),
                icon: const Icon(Icons.merge_type),
                label: const Text('Export legacy + current loans'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: loading ? null : _restoreRecord,
                icon: const Icon(Icons.restore),
                label: const Text('Restore deleted record'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: loading ? null : _deleteAllLegacy,
                icon: const Icon(Icons.delete_sweep_outlined),
                label: const Text('Delete all legacy records'),
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 12),
      const Text(
        'Use only authorised recipients when sharing bank submission ZIP files.',
      ),
    ],
  );

  Widget _login() => const Center(
    child: Padding(
      padding: EdgeInsets.all(24),
      child: Text(
        'Your LoanHub session is unavailable. Return to the main app and sign in again.',
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => BlocBuilder<LegacyBloc, LegacyState>(
    builder: (context, state) {
      final tab = state.tab.clamp(0, 2);
      return Scaffold(
        appBar: AppBar(
          title: const Text('LoanHub', overflow: TextOverflow.ellipsis),
          actions: [
            if (configured)
              IconButton(
                tooltip: 'Refresh',
                icon: const Icon(Icons.refresh),
                onPressed: loading ? null : _connect,
              ),
            const SizedBox.shrink(),
          ],
        ),
        body: Column(
          children: [
            if (loading) const LinearProgressIndicator(minHeight: 3),
            if (error != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (configured)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: ListTile(
                  leading: const Icon(Icons.business_outlined),
                  title: Text(
                    companyNames[companyId.text] ?? 'Active LoanHub company',
                  ),
                  subtitle: const Text(
                    'Company selection is managed by the main LoanHub app',
                  ),
                  dense: true,
                ),
              ),
            Expanded(
              child: !configured
                  ? _login()
                  : IndexedStack(
                      index: tab,
                      children: [_capture(), _records(), _tools()],
                    ),
            ),
          ],
        ),
        bottomNavigationBar: configured
            ? NavigationBar(
                selectedIndex: tab,
                onDestinationSelected: (index) =>
                    context.read<LegacyBloc>().add(LegacyTabSelected(index)),
                destinations: const [
                  NavigationDestination(
                    icon: Icon(Icons.add_circle_outline),
                    label: 'Capture',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.table_rows_outlined),
                    label: 'Records',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.file_download_outlined),
                    label: 'Files',
                  ),
                ],
              )
            : null,
      );
    },
  );

  @override
  void dispose() {
    shuttingDown = true;
    realtimeRetry?.cancel();
    unawaited(realtimeSocket?.close() ?? Future<void>.value());
    for (final c in [
      apiUrl,
      token,
      companyId,
      name,
      employer,
      account,
      amount,
      search,
    ]) {
      c.dispose();
    }
    super.dispose();
  }
}
