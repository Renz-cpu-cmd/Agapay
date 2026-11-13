import 'dart:convert';
import '../../core/ui.dart';

/// Resident-only data rights. Nothing is sent until the owner explicitly submits.
class PrivacyScreen extends StatefulWidget {
  const PrivacyScreen({super.key});
  @override
  State<PrivacyScreen> createState() => _PrivacyScreenState();
}

class _PrivacyScreenState extends State<PrivacyScreen> {
  final _password = TextEditingController();
  Map<String, dynamic>? _notice;
  List<dynamic> _cases = [];
  String _kind = 'access';
  String? _error, _message, _copy;
  bool _busy = false;
  int? _owner, _next = 0;
  int _generation = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final owner = AppScope.of(context).user?.id;
    if (_owner == owner) return;
    _owner = owner;
    _generation++;
    _password.clear();
    _busy = false;
    _message = null;
    _copy = null;
    _cases = [];
    _notice = null;
    _error = null;
    _next = 0;
    _load();
  }

  Future<void> _load() async {
    final generation = ++_generation;
    final app = AppScope.of(context);
    try {
      final notice = await app.auth.request('privacy/notice');
      final cases = await app.auth.request('privacy/cases');
      if (mounted && generation == _generation && _owner == app.user?.id) {
        setState(() {
          _notice = (notice as Map).cast<String, dynamic>();
          _cases = cases as List;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted && generation == _generation) {
        setState(() {
          _notice = null;
          _cases = [];
          _error =
              'Privacy service unavailable. No approved policy or received request can be confirmed.';
        });
      }
    }
  }

  Future<void> _submit({bool export = false}) async {
    if (_busy || _password.text.isEmpty) return;
    final app = AppScope.of(context),
        owner = _owner,
        generation = ++_generation;
    final password = _password.text;
    _password.clear();
    setState(() {
      _busy = true;
      _error = null;
      _message = null;
      _copy = null;
    });
    try {
      final result = await app.auth.request(
        export
            ? 'privacy/export?after=${_next ?? 0}&limit=50'
            : 'privacy/cases',
        method: 'POST',
        body: {'current_password': password, if (!export) 'kind': _kind},
      );
      if (!mounted || generation != _generation || owner != app.user?.id) {
        return;
      }
      final value = (result as Map).cast<String, dynamic>();
      setState(() {
        if (export) {
          _copy = const JsonEncoder.withIndent('  ').convert(value);
          _next = value['next_after'] as int?;
          _message =
              'Own-record page loaded. This contains personal information. Additional retained evidence requires an access review.';
        } else {
          _cases = [value, ..._cases.where((row) => row['id'] != value['id'])];
          _message =
              'Request recorded: ${value['id']}. This is a review request, not confirmation of erasure.';
        }
      });
    } catch (error) {
      if (mounted && generation == _generation && owner == app.user?.id) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted && generation == _generation) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    ++_generation;
    _password.dispose();
    _copy = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final deployment = _notice?['deployment'] as Map?;
    final policy = _notice?['policy'] as Map?;
    return Scaffold(
      body: SafeArea(
        child: PageContent(
          children: [
            PageHeading(
              'Privacy & data requests',
              'Personal data, retention and review',
              onBack: () => Navigator.pop(context),
            ),
            if (!app.signedIn)
              const Text('Sign in again to view private requests.')
            else ...[
              Text(
                _notice == null
                    ? 'Privacy information unavailable until loaded.'
                    : deployment?['status'] == 'organization_attested'
                    ? 'Organization-attested policy record'
                    : 'Unapproved development policy',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                _notice?['limits'] as String? ??
                    'No approved deployment policy can be confirmed.',
              ),
              Text(
                'Privacy contact: ${deployment?['privacy_contact'] ?? 'Not assigned; public deployment pending'}. ${deployment?['operator_hours'] ?? 'No operational response hours committed'}.',
              ),
              ExpansionTile(
                title: const Text('Data, recipients and retention'),
                children: [
                  for (final item in (_notice?['data'] as List? ?? []))
                    ListTile(title: Text(item.toString())),
                  for (final item in (_notice?['recipients'] as List? ?? []))
                    ListTile(title: Text(item.toString())),
                  Text(
                    'Development defaults: resolved SOS coordinates and free text ${policy?['resolved_sos_location_days'] ?? 'unknown'} days; remaining resident snapshot ${policy?['resolved_sos_narrative_days'] ?? 'unknown'} days. Open incidents and justified holds are excluded. Backups and external copies require separate review.',
                  ),
                ],
              ),
              const Text(
                'Request access, correction or erasure review. Application erasure disables the account after review. An unresolved SOS or justified hold can defer it. Keep the case reference for follow-up; no operational response SLA is promised.',
              ),
              TextField(
                controller: _password,
                obscureText: true,
                autofillHints: const [AutofillHints.password],
                maxLength: 128,
                decoration: const InputDecoration(
                  labelText: 'Current password',
                ),
              ),
              DropdownButtonFormField<String>(
                initialValue: _kind,
                itemHeight: null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Request type'),
                items: const [
                  DropdownMenuItem(value: 'access', child: Text('Access')),
                  DropdownMenuItem(
                    value: 'correction',
                    child: Text('Correction'),
                  ),
                  DropdownMenuItem(
                    value: 'erasure',
                    child: Text('Erasure review'),
                  ),
                ],
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _kind = value!),
              ),
              TextButton(
                onPressed: _busy ? null : () => _submit(),
                child: const Text('Record privacy request'),
              ),
              TextButton(
                onPressed: _busy || _next == null
                    ? null
                    : () => _submit(export: true),
                child: Text(
                  _next == 0
                      ? 'View my record page'
                      : _next == null
                      ? 'All available pages loaded'
                      : 'View next record page',
                ),
              ),
              TextButton(
                onPressed: _busy ? null : _load,
                child: const Text('Refresh privacy requests'),
              ),
              if (_message != null)
                Semantics(liveRegion: true, child: Text(_message!)),
              if (_error != null)
                Semantics(liveRegion: true, child: Text(_error!)),
              for (final row in _cases)
                Panel(
                  child: Text(
                    '${row['kind']} · ${row['state']}\nReference ${row['id']}\nReview target ${row['due_at']}',
                  ),
                ),
              if (_copy != null) ...[
                const Text(
                  'Personal record copy — not saved to general application storage. Selection/copy is an explicit sharing action; protect any copy you retain.',
                ),
                SelectableText(_copy!),
                TextButton(
                  onPressed: () => setState(() => _copy = null),
                  child: const Text('Clear record copy from screen'),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}
