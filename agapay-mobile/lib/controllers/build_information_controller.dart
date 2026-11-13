import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../core/release_configuration.dart';

class BuildInformationController extends ChangeNotifier {
  BuildInformationController({Future<PackageInfo> Function()? load})
    : _load = load ?? PackageInfo.fromPlatform;
  final Future<PackageInfo> Function() _load;
  String label = 'Build information unavailable';
  bool _disposed = false;
  Future<void> refresh() async {
    try {
      final info = await _load();
      if (!_disposed) {
        label =
            'Version ${info.version} · Build ${info.buildNumber.isEmpty ? 'unspecified' : info.buildNumber}${ReleaseConfiguration.releaseId.isEmpty ? '' : ' · ${ReleaseConfiguration.environment} · ${ReleaseConfiguration.releaseId} · ${ReleaseConfiguration.revision.substring(0, 8)}'}';
      }
    } catch (_) {
      /* Never invent a fallback release number. */
    }
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
