import '../../core/ui.dart';
import 'resource_instructions.dart';

class OfflineReaderBanner extends StatefulWidget {
  const OfflineReaderBanner({super.key});
  @override
  State<OfflineReaderBanner> createState() => _OfflineReaderBannerState();
}

class _OfflineReaderBannerState extends State<OfflineReaderBanner> {
  bool _busy = false;
  String? _error;
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    if (!app.signedIn) return const SizedBox.shrink();
    if (!app.auth.offlineReader && !app.auth.hasCachedReads) {
      return app.auth.cacheWarning == null
          ? const SizedBox.shrink()
          : Material(
              color: context.colors.surfaceRaised,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: tx(
                  'OFFLINE SAVING UNAVAILABLE · ${app.auth.cacheWarning}',
                  size: 11,
                ),
              ),
            );
    }
    return Material(
      color: context.colors.surfaceRaised,
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            tx(
              app.auth.offlineReader
                  ? 'OFFLINE READER · LAST KNOWN · NOT LIVE'
                  : 'LAST KNOWN DATA · SOME FEEDS UNAVAILABLE',
              size: 12,
              weight: 800,
            ),
            tx(
              app.auth.offlineReader
                  ? 'Session and current conditions are unconfirmed. No SOS is sent automatically. Exiting this reader clears local access; it does not revoke server sessions or push.'
                  : 'Some data is last known with original timestamps. A feed outage does not confirm current conditions or SOS receipt. No saved SOS is sent automatically.',
              size: 10,
            ),
            if (_error != null)
              tx(_error!, size: 11, color: context.colors.red),
            Wrap(
              spacing: 8,
              children: [
                TextButton(
                  onPressed: _busy
                      ? null
                      : () async {
                          setState(() {
                            _busy = true;
                            _error = null;
                          });
                          try {
                            await app.verifyConnection();
                            await Future.wait([
                              app.monitoring.refresh(),
                              app.resources.refresh(),
                              app.sos.refresh(),
                              app.communityAlerts.refreshActive(),
                            ]);
                          } catch (_) {
                            if (mounted) {
                              setState(
                                () => _error =
                                    'Connection could not be verified. The reader remains unconfirmed.',
                              );
                            }
                          } finally {
                            if (mounted) setState(() => _busy = false);
                          }
                        },
                  child: Text(
                    _busy ? 'Checking…' : 'Verify connection & refresh',
                  ),
                ),
                TextButton(
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    builder: (_) => AppScope(
                      controller: app,
                      child: const SafeArea(
                        child: SingleChildScrollView(
                          child: PreparednessPanel(),
                        ),
                      ),
                    ),
                  ),
                  child: const Text('Saved preparedness'),
                ),
                if (app.communityAlerts.lastReadId != null)
                  TextButton(
                    onPressed: () =>
                        app.showCommunityAlert(app.communityAlerts.lastReadId!),
                    child: const Text('Continue saved episode'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
