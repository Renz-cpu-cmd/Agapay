import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/response_resource.dart';
import '../services/auth_api.dart';

class ResponseResourceController extends ChangeNotifier {
  ResponseResourceController(this.api);
  final AuthApi api;
  int? _owner;
  int _generation = 0;
  bool _disposed = false, busy = false, _foreground = true;
  String? areaId;
  final checkedAt = <String, DateTime>{};
  final offsets = <String, int>{};
  bool isCurrent(String kind) =>
      _foreground &&
      cached[kind] != true &&
      errors[kind] == null &&
      checkedAt[kind] != null &&
      !DateTime.now().isBefore(checkedAt[kind]!) &&
      DateTime.now().difference(checkedAt[kind]!) <=
          const Duration(seconds: 90);
  Timer? _timer;
  final items = <String, List<ResponseResource>>{};
  final cached = <String, bool>{};
  final errors = <String, String>{};
  final totals = <String, int>{};
  final savedAt = <String, DateTime?>{};
  static const kinds = ['shelter', 'road', 'preparedness'];
  void setOwner(int? owner) {
    if (_disposed || _owner == owner) return;
    _owner = owner;
    ++_generation;
    _timer?.cancel();
    busy = false;
    items.clear();
    cached.clear();
    errors.clear();
    totals.clear();
    savedAt.clear();
    checkedAt.clear();
    offsets.clear();
    notifyListeners();
    if (owner != null && _foreground) {
      unawaited(refresh());
      _timer = Timer.periodic(
        const Duration(seconds: 30),
        (_) => unawaited(refresh()),
      );
    }
  }

  void setArea(String? area) {
    if (_disposed || area == areaId) return;
    areaId = area;
    ++_generation;
    busy = false;
    items.clear();
    cached.clear();
    errors.clear();
    totals.clear();
    savedAt.clear();
    checkedAt.clear();
    offsets.clear();
    notifyListeners();
    unawaited(refresh());
  }

  void setForeground(bool value) {
    if (_disposed || value == _foreground) return;
    _foreground = value;
    ++_generation;
    busy = false;
    _timer?.cancel();
    for (final kind in kinds) {
      cached[kind] = true;
    }
    notifyListeners();
    if (value && _owner != null) {
      unawaited(refresh());
      _timer = Timer.periodic(
        const Duration(seconds: 30),
        (_) => unawaited(refresh()),
      );
    }
  }

  Future<void> refresh({String? kind, int? offset}) async {
    if (_disposed || _owner == null || busy || !_foreground) return;
    if (kind != null && !kinds.contains(kind)) return;
    if (kind != null && offset != null) {
      offsets[kind] = offset.clamp(0, 50000);
      items.remove(kind);
      checkedAt.remove(kind);
    }

    busy = true;
    final generation = _generation;
    await Future.wait(
      (kind == null ? kinds : [kind]).map((kind) async {
        final path =
            'response-resources?kind=$kind&limit=100&offset=${offsets[kind] ?? 0}${areaId == null ? '' : '&area_id=${Uri.encodeQueryComponent(areaId!)}'}';
        try {
          final raw = await api.request(path) as Map;
          final next = (raw['items'] as List)
              .map(
                (e) => ResponseResource.fromJson(
                  (e as Map).cast<String, dynamic>(),
                ),
              )
              .toList();
          if (_disposed || generation != _generation) return;
          if (next.any(
            (row) =>
                row.kind != kind ||
                row.raw['mode'] != 'Actual' ||
                (areaId != null &&
                    !(row.raw['area_ids'] as List? ?? []).contains(areaId)),
          )) {
            throw const FormatException('Response resource scope mismatch');
          }
          items[kind] = next;
          checkedAt[kind] = DateTime.now();
          totals[kind] = raw['total'] as int;
          cached[kind] = api.wasCached(path);
          savedAt[kind] = api.cachedAt(path);
          errors.remove(kind);
        } catch (_) {
          if (_disposed || generation != _generation) return;
          cached[kind] = true;
          errors[kind] =
              'Source unavailable. Any retained information is last known, not confirmed current.';
        }
      }),
    );
    if (!_disposed && generation == _generation) {
      busy = false;
      notifyListeners();
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
