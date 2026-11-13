import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show appFlavor;

/// Build-owned configuration. No passwords, service-account keys or push tokens.
abstract final class ReleaseConfiguration {
  static const environment = String.fromEnvironment(
    'AGAPAY_ENV',
    defaultValue: 'development',
  );
  static const revision = String.fromEnvironment('AGAPAY_REVISION');
  static const releaseId = String.fromEnvironment('AGAPAY_RELEASE_ID');
  static const apiOrigin = String.fromEnvironment('AGAPAY_API_URL');
  static const mapMode = String.fromEnvironment(
    'AGAPAY_MAP_MODE',
    defaultValue: 'list_only',
  );
  static const mapOrigin = String.fromEnvironment('AGAPAY_MAP_ORIGIN');
  static bool get protectedBuild =>
      kReleaseMode || environment != 'development';
  static bool get exercisesAvailable => !protectedBuild;

  static void validate() => validateValues(
    release: kReleaseMode,
    environment: environment,
    flavor: appFlavor,
    api: apiOrigin,
    revision: revision,
    releaseId: releaseId,
    mapMode: mapMode,
    mapOrigin: mapOrigin,
  );

  @visibleForTesting
  static void validateValues({
    required bool release,
    required String environment,
    required String? flavor,
    required String api,
    required String revision,
    required String releaseId,
    required String mapMode,
    required String mapOrigin,
  }) {
    if (!['development', 'staging', 'production'].contains(environment)) {
      throw StateError('Unknown application environment');
    }
    if (!release && environment == 'development') return;
    if (!['staging', 'production'].contains(environment) ||
        flavor != environment) {
      throw StateError(
        'Protected builds require a matching native staging/production flavor',
      );
    }
    publicHttps(api);
    if (!RegExp(r'^[a-f0-9]{40}$').hasMatch(revision) ||
        !RegExp(r'^[A-Za-z0-9._-]{3,100}$').hasMatch(releaseId)) {
      throw StateError('Immutable revision and release identity required');
    }
    if (!['list_only', 'hosted'].contains(mapMode)) {
      throw StateError('Unknown protected map profile');
    }
    if (mapMode == 'hosted') publicHttps(mapOrigin);
  }

  static Uri publicHttps(String value) {
    final uri = Uri.tryParse(value),
        host = Uri.tryParse(value)?.host.toLowerCase() ?? '';
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.userInfo.isNotEmpty ||
        uri.query.isNotEmpty ||
        uri.fragment.isNotEmpty ||
        !['', '/'].contains(uri.path) ||
        !host.contains('.') ||
        host.contains(':') ||
        host == 'localhost' ||
        host.endsWith('.localhost') ||
        host.endsWith('.local') ||
        RegExp(r'^\d+\.').hasMatch(host)) {
      throw StateError('A reviewed public HTTPS origin is required');
    }
    return uri;
  }
}
