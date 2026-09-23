import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/community_alert.dart';
import '../services/auth_api.dart';

/// Serializes requests per resource, dropping queued/outstanding results after
/// owner or query changes. AuthApi owns HTTP, session expiry and request timeout.
class CommunityAlertResource<T> extends ChangeNotifier {
  CommunityAlertResource(this._api, this._parse);
  final AuthApi _api;
  final T Function(Object?) _parse;
  Future<void> _tail = Future.value();
  int _version = 0;
  bool _disposed = false;
  T? data;
  bool loading = false;
  String? error;

  Future<void> load(
    String path, {
    bool clear = true,
    bool Function(T)? validate,
  }) {
    final version = ++_version;
    if (clear) data = null;
    error = null;
    loading = true;
    notifyListeners();
    return _tail = _tail.then((_) async {
      if (_disposed || version != _version) return;
      try {
        final raw = await _api.request(path);
        if (_disposed || version != _version) return;
        final parsed = _parse(raw);
        if (validate != null && !validate(parsed)) {
          throw const FormatException('Unexpected alert response');
        }
        data = parsed;
      } catch (_) {
        if (_disposed || version != _version) return;
        data = null;
        error = 'Alert service is currently unavailable.';
      } finally {
        if (!_disposed && version == _version) {
          loading = false;
          notifyListeners();
        }
      }
    });
  }

  void clear() {
    ++_version;
    data = null;
    error = null;
    loading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    ++_version;
    super.dispose();
  }
}

class CommunityAlertController extends ChangeNotifier {
  CommunityAlertController(AuthApi api)
    : active = CommunityAlertResource(api, CommunityAlertPage.fromJson),
      history = CommunityAlertResource(api, CommunityAlertPage.fromJson),
      detail = CommunityAlertResource(api, CommunityAlertDetail.fromJson) {
    active.addListener(notifyListeners);
    history.addListener(notifyListeners);
    detail.addListener(notifyListeners);
  }
  static const pageSize = 50;
  final CommunityAlertResource<CommunityAlertPage> active, history;
  final CommunityAlertResource<CommunityAlertDetail> detail;
  Timer? _poll;
  int? _owner;
  bool _disposed = false;
  int activeOffset = 0, historyOffset = 0, transitionOffset = 0;
  int? selectedId;

  void setOwner(int? owner) {
    if (_disposed || _owner == owner) return;
    _owner = owner;
    _poll?.cancel();
    activeOffset = historyOffset = transitionOffset = 0;
    selectedId = null;
    active.clear();
    history.clear();
    detail.clear();
    if (owner != null) {
      unawaited(refreshActive());
      _poll = Timer.periodic(const Duration(seconds: 5), (_) {
        if (!active.loading) unawaited(refreshActive());
      });
    }
  }

  Future<void> refreshActive({int? offset}) async {
    if (_owner == null || _disposed || active.loading) return;
    final changed = offset != null && offset != activeOffset;
    activeOffset = offset ?? activeOffset;
    await active.load(
      'community-alerts/active?limit=$pageSize&offset=$activeOffset',
      clear: changed,
      validate: (page) => page.items.every((a) => !a.isResolved),
    );
  }

  Future<void> refreshHistory({int? offset}) async {
    if (_owner == null || _disposed) return;
    historyOffset = offset ?? historyOffset;
    // History includes ACTIVE and RESOLVED episodes; replace bounded pages,
    // never accumulate offset results that can shift during ingestion.
    await history.load(
      'community-alerts?limit=$pageSize&offset=$historyOffset',
    );
  }

  Future<void> openDetail(int id, {int offset = 0}) async {
    if (_owner == null || _disposed) return;
    selectedId = id;
    transitionOffset = offset;
    await detail.load(
      'community-alerts/$id?transition_limit=$pageSize&transition_offset=$offset',
      validate: (value) => value.episode.id == id,
    );
  }

  void closeDetail() {
    selectedId = null;
    transitionOffset = 0;
    detail.clear();
  }

  @override
  void dispose() {
    _disposed = true;
    _poll?.cancel();
    for (final resource in [active, history, detail]) {
      resource.removeListener(notifyListeners);
      resource.dispose();
    }
    super.dispose();
  }
}
