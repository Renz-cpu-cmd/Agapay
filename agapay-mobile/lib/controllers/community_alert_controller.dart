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
  bool loading = false, cached = false;
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
        cached = _api.wasCached(path);
        if (cached) {
          error =
              'OFFLINE · Last-known episode. Current hazard and response status are unconfirmed.';
        }
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

  void pause() {
    ++_version;
    loading = false;
    notifyListeners();
  }

  void clear() {
    ++_version;
    data = null;
    cached = false;
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
    : _api = api,
      active = CommunityAlertResource(api, CommunityAlertPage.fromJson),
      history = CommunityAlertResource(api, CommunityAlertPage.fromJson),
      detail = CommunityAlertResource(api, CommunityAlertDetail.fromJson) {
    active.addListener(notifyListeners);
    history.addListener(notifyListeners);
    detail.addListener(notifyListeners);
  }
  final AuthApi _api;
  int? lastReadId;
  int _readerGeneration = 0;
  static const pageSize = 50;
  final CommunityAlertResource<CommunityAlertPage> active, history;
  final CommunityAlertResource<CommunityAlertDetail> detail;
  Timer? _poll;
  int? _owner;
  bool _disposed = false;
  int activeOffset = 0, historyOffset = 0, transitionOffset = 0;
  int? selectedId;

  bool _foreground = true;
  void setForeground(bool value) {
    if (_disposed || _foreground == value) return;
    _foreground = value;
    _poll?.cancel();
    if (!value) {
      active.pause();
      history.pause();
      detail.pause();
      return;
    }
    if (_owner != null) {
      unawaited(refreshActive());
      _startPoll();
    }
  }

  void _startPoll() {
    _poll?.cancel();
    if (!_foreground || _owner == null) return;
    _poll = Timer.periodic(const Duration(seconds: 10), (_) {
      if (!active.loading) unawaited(refreshActive());
    });
  }

  void setOwner(int? owner) {
    if (_disposed || _owner == owner) return;
    _owner = owner;
    final generation = ++_readerGeneration;
    _poll?.cancel();
    activeOffset = historyOffset = transitionOffset = 0;
    selectedId = null;
    lastReadId = null;
    active.clear();
    history.clear();
    detail.clear();
    if (owner != null) {
      active.loading = true;
      unawaited(_restoreReader(owner, generation));
      _startPoll();
    }
  }

  Future<void> _restoreReader(int owner, int generation) async {
    final state = await _api.restoreReaderState();
    if (_disposed || _owner != owner || generation != _readerGeneration) return;
    lastReadId = state?['last_episode_id'] as int?;
    activeOffset = (state?['active_offset'] as int? ?? 0).clamp(0, 50000);
    historyOffset = (state?['history_offset'] as int? ?? 0).clamp(0, 50000);
    active.loading = false;
    notifyListeners();
    await refreshActive();
  }

  Future<void> refreshActive({int? offset}) async {
    if (_owner == null || _disposed || active.loading || !_foreground) return;
    final changed = offset != null && offset != activeOffset;
    activeOffset = offset ?? activeOffset;
    if (offset != null) {
      unawaited(_api.saveReaderState({'active_offset': activeOffset}));
    }
    await active.load(
      'community-alerts/active?limit=$pageSize&offset=$activeOffset',
      clear: changed,
      validate: (page) => page.items.every((a) => !a.isResolved),
    );
  }

  Future<void> refreshHistory({int? offset}) async {
    if (_owner == null || _disposed) return;
    historyOffset = offset ?? historyOffset;
    if (offset != null) {
      unawaited(_api.saveReaderState({'history_offset': historyOffset}));
    }
    await history.load(
      'community-alerts?limit=$pageSize&offset=$historyOffset',
    );
  }

  Future<void> openDetail(int id, {int offset = 0}) async {
    if (_owner == null || _disposed) return;
    selectedId = id;
    lastReadId = id;
    unawaited(_api.saveReaderState({'last_episode_id': id}));
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
