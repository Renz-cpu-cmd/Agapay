import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/official_notice.dart';
import '../services/auth_api.dart';

class NoticeFeed {
  List<OfficialNotice> items = const [];
  DateTime? checkedAt;
  bool loading = false, cached = false, hasMore = false;
  String? error;
}

/// One account/area-scoped reader for home and alerts. History cannot replace
/// the current feed, and late responses cannot cross account or area changes.
class OfficialNoticeController extends ChangeNotifier {
  OfficialNoticeController(this.api, {DateTime Function()? now})
    : now = now ?? DateTime.now;
  final AuthApi api;
  final DateTime Function() now;
  NoticeFeed current = NoticeFeed(), history = NoticeFeed();
  int? _owner;
  String? areaId;
  int _generation = 0, _historyRequest = 0, historyOffset = 0;
  bool _foreground = true, _disposed = false;
  Timer? _timer;
  bool confirmed(NoticeFeed feed) =>
      _foreground &&
      !feed.cached &&
      feed.error == null &&
      feed.checkedAt != null &&
      !now().isBefore(feed.checkedAt!) &&
      now().difference(feed.checkedAt!) <= const Duration(seconds: 90);

  void setScope(int? owner, String? area) {
    if (_disposed || (_owner == owner && areaId == area)) return;
    _owner = owner;
    areaId = area;
    ++_generation;
    ++_historyRequest;
    current = NoticeFeed();
    history = NoticeFeed();
    historyOffset = 0;
    _timer?.cancel();
    notifyListeners();
    if (owner != null && area != null && _foreground) {
      unawaited(refresh());
      _startTimer();
    }
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_disposed) return;
      notifyListeners(); // Age/expiry advances even when requests fail.
      if (timer.tick % 30 == 0) unawaited(refresh());
    });
  }

  void setForeground(bool value) {
    if (_disposed || _foreground == value) return;
    _foreground = value;
    ++_generation;
    ++_historyRequest;
    _timer?.cancel();
    current.loading = history.loading = false;
    // A resumed page must be checked again before displaying current advice.
    current.cached = history.cached = true;
    notifyListeners();
    if (value && _owner != null && areaId != null) {
      unawaited(refresh());
      _startTimer();
    }
  }

  Future<void> refresh({bool past = false, int? offset}) async {
    if (_disposed || !_foreground || _owner == null || areaId == null) return;
    final feed = past ? history : current;
    if (feed.loading && offset == null) return;
    final generation = _generation;
    final request = past ? ++_historyRequest : 0;
    if (past && offset != null) {
      historyOffset = offset;
      feed.items = const [];
      feed.checkedAt = null;
    }
    final area = areaId!;
    final path =
        'official-notices?limit=50&offset=${past ? historyOffset : 0}&area_id=${Uri.encodeQueryComponent(area)}&status=Actual&current_only=${!past}';
    feed.loading = true;
    notifyListeners();
    bool valid() =>
        !_disposed &&
        generation == _generation &&
        (!past || request == _historyRequest);
    try {
      final raw = await api.request(path) as Map;
      final checked = DateTime.parse(raw['checked_at'] as String);
      final scope = raw['scope'] as Map;
      if (scope['area_id'] != area ||
          scope['status'] != 'Actual' ||
          scope['current_only'] != !past) {
        throw const FormatException('Notice scope mismatch');
      }
      final rows = (raw['items'] as List)
          .map(
            (r) => OfficialNotice.fromJson((r as Map).cast<String, dynamic>()),
          )
          .toList();
      if (rows.any((n) => n.status != 'Actual' || !n.areaIds.contains(area))) {
        throw const FormatException('Notice outside requested scope');
      }
      if (!valid()) return;
      feed.items = List.unmodifiable(rows);
      feed.checkedAt = checked;
      feed.cached = api.wasCached(path);
      feed.hasMore = raw['has_more'] == true;
      feed.error = null;
    } catch (_) {
      if (!valid()) return;
      feed.error =
          'Notice updates unavailable. Confirm current instructions with the issuing authority.';
    } finally {
      if (valid()) {
        feed.loading = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    _timer?.cancel();
    super.dispose();
  }
}
