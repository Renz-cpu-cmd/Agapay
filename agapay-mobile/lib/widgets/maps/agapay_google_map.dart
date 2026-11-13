import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../core/ui.dart';
import '../../core/release_configuration.dart';

const _htmlAsset = 'assets/maps/agapay_google_map.html';
const _demoKeyAsset = 'assets/config/google_maps_demo_key.txt';

class AgapayMapCoordinate {
  const AgapayMapCoordinate(this.latitude, this.longitude);

  final double latitude;
  final double longitude;

  Map<String, double> toJson() => {
    'latitude': latitude,
    'longitude': longitude,
  };
}

class AgapayGoogleMapRoute {
  const AgapayGoogleMapRoute({
    required this.id,
    required this.origin,
    required this.destination,
    this.travelMode = 'WALKING',
  });

  final String id;
  final AgapayMapCoordinate origin;
  final AgapayMapCoordinate destination;
  final String travelMode;

  Map<String, Object> toJson() => {
    'id': id,
    'origin': origin.toJson(),
    'destination': destination.toJson(),
    'travelMode': travelMode,
  };
}

class AgapayGoogleMapRouteUpdate {
  const AgapayGoogleMapRouteUpdate({
    required this.id,
    required this.status,
    this.distanceMeters,
    this.durationSeconds,
    this.message,
    this.warnings = const [],
  });

  final String id;
  final String status;
  final double? distanceMeters;
  final int? durationSeconds;
  final String? message;
  final List<String> warnings;
}

class AgapayGoogleMapMarker {
  const AgapayGoogleMapMarker({
    required this.id,
    required this.title,
    required this.position,
    required this.color,
    required this.glyph,
    this.selected = false,
  });

  final String id;
  final String title;
  final AgapayMapCoordinate position;
  final Color color;
  final String glyph;
  final bool selected;

  String get _hexColor =>
      '#${color.toARGB32().toRadixString(16).padLeft(8, '0').substring(2)}';

  Map<String, Object> toJson() => {
    'id': id,
    'title': title,
    'position': position.toJson(),
    'color': _hexColor,
    'glyph': glyph,
    'selected': selected,
  };
}

class AgapayGoogleMapPolyline {
  const AgapayGoogleMapPolyline({
    required this.id,
    required this.title,
    required this.points,
    required this.color,
  });
  final String id, title;
  final List<AgapayMapCoordinate> points;
  final String color;
  Map<String, Object> toJson() => {
    'id': id,
    'title': title,
    'points': points.map((p) => p.toJson()).toList(),
    'color': color,
  };
}

class AgapayGoogleMap extends StatefulWidget {
  const AgapayGoogleMap({
    super.key,
    required this.center,
    required this.markers,
    this.overlays = const [],
    this.route,
    this.zoom = 15,
    this.focusZoom,
    this.tilt = 42,
    this.fitAll = false,
    this.selectedMarkerId,
    this.onMarkerTap,
    this.onRouteUpdate,
  });

  final AgapayMapCoordinate center;
  final List<AgapayGoogleMapMarker> markers;
  final List<AgapayGoogleMapPolyline> overlays;
  final AgapayGoogleMapRoute? route;
  final double zoom;

  /// Zoom for the selected marker. Null keeps the page's close-up (17); A7.1 passes a
  /// wider value for an approximate position so its whole area is visible.
  final double? focusZoom;
  final double tilt;
  final bool fitAll;
  final String? selectedMarkerId;
  final ValueChanged<String>? onMarkerTap;
  final ValueChanged<AgapayGoogleMapRouteUpdate>? onRouteUpdate;

  @override
  State<AgapayGoogleMap> createState() => _AgapayGoogleMapState();
}

class _AgapayGoogleMapState extends State<AgapayGoogleMap> {
  WebViewController? _controller;
  String? _apiKey;
  String? _html;
  String? _error;
  bool _pageLoaded = false;
  bool _ready = false;
  bool _dark = false;
  Timer? _watchdog;

  /// A load that never settles (script or tiles stalled) must end in the readable
  /// retry state, not an endless spinner. Only armed when a real WebView exists.
  void _armWatchdog() {
    if (_controller == null) return;
    _watchdog?.cancel();
    _watchdog = Timer(const Duration(seconds: 30), () {
      if (!mounted || _ready || _error != null) return;
      setState(
        () => _error =
            'Google Maps did not finish loading. Check the connection and retry; station details remain available.',
      );
    });
  }

  @override
  void dispose() {
    _watchdog?.cancel();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    try {
      _controller = WebViewController();
    } catch (_) {
      // Widget tests and unsupported desktop targets do not provide a WebView.
    }
    final controller = _controller;
    if (controller != null) _configure(controller);
  }

  Future<void> _configure(WebViewController controller) async {
    await controller.setJavaScriptMode(JavaScriptMode.unrestricted);
    await controller.setBackgroundColor(AppPalette(_dark).surface);
    await controller.addJavaScriptChannel(
      'AgapayBridge',
      onMessageReceived: _onJavaScriptMessage,
    );
    await controller.setNavigationDelegate(
      NavigationDelegate(
        onPageFinished: (_) {
          // Any (re)loaded page starts a fresh map, including reloads the app did not
          // start; it is not ready until the page says so, and the watchdog bounds it.
          _pageLoaded = true;
          if (mounted && _ready) setState(() => _ready = false);
          _armWatchdog();
          _render();
        },
        onNavigationRequest: (request) {
          if (ReleaseConfiguration.protectedBuild && request.isMainFrame) {
            final allowed = Uri.tryParse(ReleaseConfiguration.mapOrigin),
                target = Uri.tryParse(request.url);
            if (allowed == null ||
                target == null ||
                target.scheme != 'https' ||
                allowed.origin != target.origin) {
              return NavigationDecision.prevent;
            }
          }
          return NavigationDecision.navigate;
        },
        onWebResourceError: (error) {
          if (error.isForMainFrame == true && mounted) {
            setState(() {
              _ready = false;
              _error = 'The Google map page could not load.';
            });
          }
        },
      ),
    );
    await _loadAssets();
  }

  Future<void> _loadAssets() async {
    final controller = _controller;
    if (controller == null) return;
    if (mounted) {
      setState(() {
        _error = null;
        _ready = false;
        _pageLoaded = false;
      });
    }
    _armWatchdog();
    try {
      if (ReleaseConfiguration.protectedBuild) {
        if (ReleaseConfiguration.mapMode != 'hosted') {
          throw const FormatException(
            'Interactive map unavailable in this build. Use the station and shelter lists.',
          );
        }
        final origin = ReleaseConfiguration.publicHttps(
          ReleaseConfiguration.mapOrigin,
        );
        await controller.loadRequest(origin);
        return;
      }
      final values = await Future.wait([
        rootBundle.loadString(_htmlAsset),
        rootBundle.loadString(_demoKeyAsset),
      ]);
      final key = values[1].trim();
      if (key.isEmpty || key == 'PASTE_YOUR_MAPS_DEMO_KEY_HERE') {
        throw const FormatException('Google Maps key is not configured.');
      }
      _html = values[0];
      _apiKey = key;
      await controller.loadHtmlString(_html!, baseUrl: 'https://agapay.local/');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is FormatException
            ? error.message
            : 'Google Maps key is not available in this build.';
      });
    }
  }

  void _onJavaScriptMessage(JavaScriptMessage message) {
    try {
      final data = jsonDecode(message.message) as Map<String, dynamic>;
      switch (data['type']) {
        case 'ready':
          _watchdog?.cancel();
          if (mounted && !_ready) {
            setState(() {
              _ready = true;
              _error = null;
            });
          }
        case 'error':
          _watchdog?.cancel();
          if (mounted) {
            setState(() {
              _ready = false;
              _error =
                  data['message'] as String? ?? 'Google Maps could not load.';
            });
          }
        case 'marker':
          final id = data['id'] as String?;
          if (id != null) widget.onMarkerTap?.call(id);
        case 'route':
          final id = data['id'] as String?;
          final status = data['status'] as String?;
          if (id == null || status == null) return;
          widget.onRouteUpdate?.call(
            AgapayGoogleMapRouteUpdate(
              id: id,
              status: status,
              distanceMeters: (data['distanceMeters'] as num?)?.toDouble(),
              durationSeconds: (data['durationSeconds'] as num?)?.round(),
              message: data['message'] as String?,
              warnings:
                  (data['warnings'] as List<dynamic>?)
                      ?.whereType<String>()
                      .toList() ??
                  const [],
            ),
          );
      }
    } catch (_) {
      // Ignore malformed messages from the embedded page.
    }
  }

  Future<void> _render() async {
    final controller = _controller;
    final key = _apiKey;
    if (controller == null ||
        !_pageLoaded ||
        (!ReleaseConfiguration.protectedBuild && key == null)) {
      return;
    }
    final config = {
      if (!ReleaseConfiguration.protectedBuild) 'apiKey': key,
      'theme': _dark ? 'dark' : 'light',
      'center': widget.center.toJson(),
      'zoom': widget.zoom,
      'focusZoom': widget.focusZoom,
      'tilt': widget.tilt,
      'fitAll': widget.fitAll,
      'selectedMarkerId': widget.selectedMarkerId,
      'markers': widget.markers.map((marker) => marker.toJson()).toList(),
      'overlays': widget.overlays.map((line) => line.toJson()).toList(),
      'route': widget.route?.toJson(),
    };
    try {
      await controller.runJavaScript(
        'window.agapayRender(${jsonEncode(config)});',
      );
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'The embedded Google map could not be updated.',
        );
      }
    }
  }

  String _signature(AgapayGoogleMap value) => jsonEncode({
    'center': value.center.toJson(),
    'zoom': value.zoom,
    'focusZoom': value.focusZoom,
    'tilt': value.tilt,
    'fitAll': value.fitAll,
    'selectedMarkerId': value.selectedMarkerId,
    'markers': value.markers.map((marker) => marker.toJson()).toList(),
    'overlays': value.overlays.map((line) => line.toJson()).toList(),
    'route': value.route?.toJson(),
  });

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final next = context.colors.isDark;
    if (next == _dark) return;
    _dark = next;
    _ready = false;
    _armWatchdog();
    _controller?.setBackgroundColor(context.colors.surface);
    _render();
  }

  /// The signature without marker labels. Labels carry live values (heartbeat age,
  /// measurement time) that change every second; they are refreshed in place by the
  /// page and must not hide the map behind the loading overlay.
  String _structure(AgapayGoogleMap value) => jsonEncode({
    'center': value.center.toJson(),
    'zoom': value.zoom,
    'focusZoom': value.focusZoom,
    'tilt': value.tilt,
    'fitAll': value.fitAll,
    'selectedMarkerId': value.selectedMarkerId,
    'markers': value.markers.map((marker) => marker.toJson()..remove('title')).toList(),
    'overlays': value.overlays.map((line) => line.toJson()).toList(),
    'route': value.route?.toJson(),
  });

  @override
  void didUpdateWidget(covariant AgapayGoogleMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_signature(widget) == _signature(oldWidget)) return;
    if (_structure(widget) != _structure(oldWidget)) {
      _ready = false;
      _armWatchdog();
    }
    _render();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (controller == null) {
      return ColoredBox(
        color: context.colors.surface,
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.map_outlined,
                  color: context.colors.secondary,
                  size: 34,
                ),
                const SizedBox(height: 10),
                tx(
                  'Interactive map unavailable in this preview',
                  size: 13,
                  weight: 600,
                  align: TextAlign.center,
                ),
                const SizedBox(height: 6),
                tx(
                  'For interactive maps, use the Android app. Text details remain available on this screen.',
                  size: 12,
                  color: context.colors.secondary,
                  align: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      );
    }
    final error = _error;
    if (error != null) {
      return ColoredBox(
        color: context.colors.surface,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.map_outlined,
                  color: context.colors.secondary,
                  size: 34,
                ),
                const SizedBox(height: 10),
                tx(
                  error,
                  size: 12,
                  color: context.colors.secondary,
                  align: TextAlign.center,
                ),
                const SizedBox(height: 10),
                OutlinedButton(
                  onPressed: _loadAssets,
                  child: const Text('RETRY MAP'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        WebViewWidget(
          controller: controller,
          gestureRecognizers: {
            Factory<OneSequenceGestureRecognizer>(
              () => EagerGestureRecognizer(),
            ),
          },
        ),
        if (!_ready)
          IgnorePointer(
            child: ColoredBox(
              color: context.colors.surface.withValues(alpha: .72),
              child: Center(child: CircularProgressIndicator()),
            ),
          ),
      ],
    );
  }
}
