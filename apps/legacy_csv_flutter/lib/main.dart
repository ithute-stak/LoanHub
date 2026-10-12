import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const LoanHubLegacyApp());

class LoanHubLegacyApp extends StatelessWidget {
  const LoanHubLegacyApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'LoanHub • Legacy CSV',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(useMaterial3: true, colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff155e75)), scaffoldBackgroundColor: const Color(0xfff4f7fb), inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder())),
    home: const LegacyCapturePage(),
  );
}

class LegacyCapturePage extends StatefulWidget {
  const LegacyCapturePage({super.key});
  @override
  State<LegacyCapturePage> createState() => _LegacyCapturePageState();
}

class _LegacyCapturePageState extends State<LegacyCapturePage> {
  static const secure = FlutterSecureStorage();
  final apiUrl = TextEditingController(text: const String.fromEnvironment('LOANHUB_API_URL', defaultValue: 'https://loanhub.co.ls/api/v1'));
  final token = TextEditingController();
  final companyId = TextEditingController();
  final name = TextEditingController();
  final account = TextEditingController();
  final branch = TextEditingController();
  final amount = TextEditingController();
  final search = TextEditingController();
  String groupFilter = 'all';
  List<Map<String, dynamic>> groups = [];
  List<Map<String, dynamic>> rows = [];
  String? selectedGroup;
  String? error;
  bool loading = false;
  bool configured = false;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    token.text = await secure.read(key: 'token') ?? '';
    companyId.text = await secure.read(key: 'company') ?? '';
    if (token.text.isNotEmpty && companyId.text.isNotEmpty) {
      await _connect();
    }
  }

  Future<http.Response> _request(String path, {Map<String, dynamic>? body}) {
    final uri = Uri.parse('${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}$path');
    final headers = <String, String>{
      'Authorization': 'Bearer ${token.text.trim()}',
      'X-Company-ID': companyId.text.trim(),
      'Content-Type': 'application/json',
    };
    return body == null
        ? http.get(uri, headers: headers)
        : http.post(uri, headers: headers, body: jsonEncode(body));
  }

  Future<void> _connect() async {
    setState(() { loading = true; error = null; });
    try {
      final answers = await Future.wait([
        _request('/legacy-bank-deductions/work-groups'),
        _request('/legacy-bank-deductions/'),
      ]);
      if (answers.any((r) => r.statusCode >= 400)) throw Exception('Connection or permission denied. Check your company and sign-in.');
      groups = (jsonDecode(answers[0].body) as List).cast<Map<String, dynamic>>();
      rows = (jsonDecode(answers[1].body) as List).cast<Map<String, dynamic>>();
      await secure.write(key: 'token', value: token.text.trim());
      await secure.write(key: 'company', value: companyId.text.trim());
      configured = true;
    } catch (e) { error = e.toString(); }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _importCsv() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv'],
      withData: true,
    );
    if (picked == null || picked.files.isEmpty) return;
    final item = picked.files.single;
    final bytes = item.bytes;
    if (bytes == null || bytes.length > 2000000) {
      setState(() => error = 'CSV must be no larger than 2 MB.');
      return;
    }
    Future<Map<String, dynamic>> submit(bool preview) async {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}/legacy-bank-deductions/import-csv?preview=$preview'),
      );
      request.headers['Authorization'] = 'Bearer ${token.text.trim()}';
      request.headers['X-Company-ID'] = companyId.text.trim();
      request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: item.name));
      final response = await http.Response.fromStream(await request.send());
      final decoded = jsonDecode(response.body);
      if (response.statusCode >= 400) {
        throw Exception('CSV validation failed: ${response.body}');
      }
      return (decoded as Map).cast<String, dynamic>();
    }
    setState(() { loading = true; error = null; });
    try {
      final preview = await submit(true);
      if (!mounted) return;
      final issues = (preview['issues'] as List? ?? []);
      final summary = 'Ready: ${preview['valid']}  •  Rejected: ${preview['rejected']}';
      final details = issues.take(8).map((issue) => 'Row ${issue['row']}: ${issue['reason']}').join('\n');
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Review CSV import'),
          content: SingleChildScrollView(child: Text('$summary\n\n${details.isEmpty ? "All rows passed validation." : details}')),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(
              onPressed: (preview['rejected'] as num) > 0 || (preview['valid'] as num) == 0
                ? null : () => Navigator.pop(ctx, true),
              child: const Text('Import valid rows'),
            ),
          ],
        ),
      );
      if (confirmed == true) {
        final result = await submit(false);
        final listing = await _request('/legacy-bank-deductions/');
        if (listing.statusCode != 200) throw Exception('Import saved, but refresh failed.');
        rows = (jsonDecode(listing.body) as List).cast<Map<String, dynamic>>();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Imported ${result['saved']} legacy deductions.')),
          );
        }
      }
    } catch (e) {
      error = e.toString();
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _exportZip() async {
    setState(() { loading = true; error = null; });
    try {
      final response = await _request('/legacy-bank-deductions/export.zip');
      if (response.statusCode != 200) {
        throw Exception('Export unavailable. Check records and permissions.');
      }
      final directory = await getTemporaryDirectory();
      final archive = File('${directory.path}/loanhub-legacy-bank-submissions.zip');
      await archive.writeAsBytes(response.bodyBytes, flush: true);
      await Share.shareXFiles(
        [XFile(archive.path, mimeType: 'application/zip')],
        subject: 'LoanHub legacy bank deductions',
        text: 'Confidential bank submission. Share only with an authorised recipient.',
      );
    } catch (e) {
      error = e.toString();
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _save() async {
    if (selectedGroup == null || name.text.trim().isEmpty || account.text.trim().isEmpty || branch.text.trim().isEmpty || amount.text.trim().isEmpty) {
      setState(() => error = 'Complete all fields before saving.');
      return;
    }
    setState(() { loading = true; error = null; });
    try {
      final response = await _request('/legacy-bank-deductions/', body: {
        'work_group_id': selectedGroup,
        'client_name': name.text.trim(),
        'account_number': account.text.trim(),
        'branch_code': branch.text.trim(),
        'amount': amount.text.trim(),
      });
      if (response.statusCode != 201) throw Exception('Could not save record: ${response.body}');
      name.clear(); account.clear(); branch.clear(); amount.clear();
      final listing = await _request('/legacy-bank-deductions/');
      if (listing.statusCode != 200) throw Exception('Saved, but refresh failed');
      rows = (jsonDecode(listing.body) as List).cast<Map<String, dynamic>>();
    } catch (e) { error = e.toString(); }
    if (mounted) setState(() => loading = false);
  }

  List<Map<String, dynamic>> get visibleRows => rows.where((row) {
    final query = search.text.trim().toLowerCase();
    final matchesSearch = query.isEmpty || ['client_name', 'masked_account', 'branch_code', 'work_group'].any((key) => (row[key] ?? '').toString().toLowerCase().contains(query));
    final matchesGroup = groupFilter == 'all' || row['work_group_id']?.toString() == groupFilter;
    return matchesSearch && matchesGroup;
  }).toList();

  Future<void> _modifyRecord(Map<String, dynamic> row, {required bool remove}) async {
    final currentName = TextEditingController(text: row['client_name']?.toString() ?? '');
    final currentBranch = TextEditingController(text: row['branch_code']?.toString() ?? '');
    final currentAmount = TextEditingController(text: row['amount']?.toString() ?? '');
    var selected = row['work_group_id']?.toString();
    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => StatefulBuilder(builder: (ctx, refresh) => AlertDialog(
          title: Text(remove ? 'Remove legacy record?' : 'Edit legacy record'),
          content: remove
            ? Text('Remove the entry for ${row['client_name']}? It will no longer be included in future CSV exports. This action cannot be undone.')
            : SizedBox(width: 400, child: Column(mainAxisSize: MainAxisSize.min, children: [
                DropdownButtonFormField<String>(
                  initialValue: selected,
                  decoration: const InputDecoration(labelText: 'Work group'),
                  items: groups.map((g) => DropdownMenuItem(value: g['id'].toString(), child: Text(g['name'].toString()))).toList(),
                  onChanged: (v) => refresh(() => selected = v),
                ),
                const SizedBox(height: 12),
                TextField(controller: currentName, decoration: const InputDecoration(labelText: 'Client name')),
                const SizedBox(height: 12),
                TextField(controller: currentBranch, keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    decoration: const InputDecoration(labelText: 'Branch code')),
                const SizedBox(height: 12),
                TextField(controller: currentAmount, keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Deduction amount (LSL)')),
                const SizedBox(height: 8),
                const Text('Bank account number cannot be changed here. Remove and re-enter the record to change account details.'),
              ])),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(remove ? 'Remove' : 'Save changes')),
          ],
        )),
      );
      if (confirmed != true) return;
      if (!remove && (selected == null || currentName.text.trim().isEmpty || currentBranch.text.trim().isEmpty || currentAmount.text.trim().isEmpty)) {
        setState(() => error = 'Complete all edit fields.');
        return;
      }
      setState(() { loading = true; error = null; });
      final uri = Uri.parse('${apiUrl.text.replaceAll(RegExp(r"/+$"), "")}/legacy-bank-deductions/${row['id']}');
      final headers = {
        'Authorization': 'Bearer ${token.text.trim()}',
        'X-Company-ID': companyId.text.trim(),
        'Content-Type': 'application/json',
      };
      final response = remove
          ? await http.delete(uri, headers: headers)
          : await http.patch(uri, headers: headers, body: jsonEncode({
              'work_group_id': selected,
              'client_name': currentName.text.trim(),
              'branch_code': currentBranch.text.trim(),
              'amount': currentAmount.text.trim(),
            }));
      if (response.statusCode != (remove ? 204 : 200)) {
        throw Exception('Could not update record: ${response.statusCode}');
      }
      final listing = await _request('/legacy-bank-deductions/');
      if (listing.statusCode != 200) throw Exception('Update saved, but refresh failed');
      rows = (jsonDecode(listing.body) as List).cast<Map<String, dynamic>>();
    } catch (e) {
      error = e.toString();
    } finally {
      currentName.dispose(); currentBranch.dispose(); currentAmount.dispose();
      if (mounted) setState(() => loading = false);
    }
  }

  Widget field(String label, TextEditingController controller, {bool numeric = false, bool money = false}) =>
    TextField(controller: controller, keyboardType: numeric ? const TextInputType.numberWithOptions(decimal: false) : money ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
      inputFormatters: numeric ? [FilteringTextInputFormatter.digitsOnly] : money ? [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}'))] : null,
      decoration: InputDecoration(labelText: label, filled: true, fillColor: Colors.white), maxLength: numeric ? (label == 'Branch code' ? 6 : 20) : null);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('LoanHub  /  Legacy CSV Capture'), backgroundColor: Colors.white, actions: [if (configured) IconButton(tooltip: 'Refresh records', onPressed: loading ? null : _connect, icon: const Icon(Icons.refresh))]),
      body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1250), child: ListView(padding: const EdgeInsets.all(24), children: [
        Text('Legacy bank deduction register', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        Text('Capture historical deductions securely and review them in a familiar CSV-style grid.', style: TextStyle(color: Colors.blueGrey.shade700)),
        const SizedBox(height: 20),
        if (!configured) Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Connect to your LoanHub company', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12), field('LoanHub API URL', apiUrl), const SizedBox(height: 12),
          TextField(controller: token, obscureText: true, decoration: const InputDecoration(labelText: 'Existing LoanHub access token', border: OutlineInputBorder())),
          const SizedBox(height: 12), field('Company ID', companyId), const SizedBox(height: 12),
          FilledButton.icon(onPressed: loading ? null : _connect, icon: const Icon(Icons.lock_open), label: const Text('Connect securely')),
          const SizedBox(height: 8), const Text('Initial integration uses an existing authenticated token. Do not share tokens or include them in exported files.'),
        ]))),
        if (configured) LayoutBuilder(builder: (context, constraints) => Card(child: Padding(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Add legacy record', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 20)), const SizedBox(height: 16),
          DropdownButtonFormField<String>(initialValue: selectedGroup, decoration: const InputDecoration(labelText: 'Work group (loaded from LoanHub API)'), items: groups.map((g) => DropdownMenuItem(value: g['id'].toString(), child: Text('${g['name']} (${g['code']})'))).toList(), onChanged: (v) => setState(() => selectedGroup = v)),
          const SizedBox(height: 12),
          Wrap(spacing: 12, runSpacing: 12, children: [
            SizedBox(width: constraints.maxWidth > 700 ? 260 : constraints.maxWidth - 45, child: field('Client name', name)),
            SizedBox(width: constraints.maxWidth > 700 ? 220 : constraints.maxWidth - 45, child: field('Account number', account, numeric: true)),
            SizedBox(width: constraints.maxWidth > 700 ? 170 : constraints.maxWidth - 45, child: field('Branch code', branch, numeric: true)),
            SizedBox(width: constraints.maxWidth > 700 ? 170 : constraints.maxWidth - 45, child: field('Amount (LSL)', amount, money: true)),
          ]),
          FilledButton.icon(onPressed: loading ? null : _save, icon: const Icon(Icons.add_circle_outline), label: const Text('Save to LoanHub')),
        ])))),
        if (loading) const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
        if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text(error!, style: const TextStyle(color: Colors.red))),
        if (configured) ...[
          const SizedBox(height: 20), Row(children: [const Expanded(child: Text('Saved legacy records', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold))), Chip(label: Text('${rows.length} records')), const SizedBox(width: 8), OutlinedButton.icon(onPressed: loading ? null : _importCsv, icon: const Icon(Icons.upload_file), label: const Text('Import CSV')), const SizedBox(width: 8), FilledButton.icon(onPressed: loading || rows.isEmpty ? null : _exportZip, icon: const Icon(Icons.archive_outlined), label: const Text('Export bank CSV ZIP'))]),
          const SizedBox(height: 8),
          Wrap(spacing: 12, runSpacing: 12, children: [
            SizedBox(width: 320, child: TextField(
              controller: search,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(prefixIcon: Icon(Icons.search), labelText: 'Search saved records'),
            )),
            SizedBox(width: 260, child: DropdownButtonFormField<String>(
              initialValue: 'all',
              decoration: const InputDecoration(labelText: 'Filter work group'),
              items: [
                const DropdownMenuItem(value: 'all', child: Text('All work groups')),
                ...groups.map((g) => DropdownMenuItem(value: g['id'].toString(), child: Text(g['name'].toString()))),
              ],
              onChanged: (value) => setState(() => groupFilter = value ?? 'all'),
            )),
            Chip(label: Text('${visibleRows.length} shown')),
          ]),
          const SizedBox(height: 8),
          Card(clipBehavior: Clip.antiAlias, child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(
            headingRowColor: WidgetStateProperty.all(const Color(0xffe3edf4)),
            columns: const [DataColumn(label: Text('WORK GROUP')), DataColumn(label: Text('A · CLIENT NAME')), DataColumn(label: Text('B · ACCOUNT')), DataColumn(label: Text('C · BRANCH')), DataColumn(label: Text('D · AMOUNT (LSL)'), numeric: true), DataColumn(label: Text('ACTIONS'))],
            rows: visibleRows.map((row) => DataRow(cells: [
              DataCell(Text('${row['work_group']}')),
              DataCell(Text('${row['client_name']}')),
              DataCell(Text('${row['masked_account']}')),
              DataCell(Text('${row['branch_code']}')),
              DataCell(Text('${row['amount']}')),
              DataCell(Row(mainAxisSize: MainAxisSize.min, children: [
                IconButton(tooltip: 'Edit record', icon: const Icon(Icons.edit_outlined),
                    onPressed: loading ? null : () => _modifyRecord(row, remove: false)),
                IconButton(tooltip: 'Remove record', icon: const Icon(Icons.delete_outline),
                    onPressed: loading ? null : () => _modifyRecord(row, remove: true)),
              ])),
            ])).toList(),
          ))),
          const SizedBox(height: 6), const Text('Account numbers are masked in the table. Full numbers stay encrypted on the server for authorised CSV generation.'),
        ],
      ]))),
    );
  }

  @override
  void dispose() {
    for (final c in [apiUrl, token, companyId, name, account, branch, amount, search]) { c.dispose(); }
    super.dispose();
  }
}
