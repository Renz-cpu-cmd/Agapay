import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../core/ui.dart';

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

class AgapayGoogleMap extends StatefulWidget {
  const AgapayGoogleMap({
    super.key,
    required this.center,
    required this.markers,
    this.route,
    this.zoom = 15,
    this.tilt = 42,
    this.fitAll = false,
    this.selectedMarkerId,
    this.onMarkerTap,
    this.onRouteUpdate,
  });

  final AgapayMapCoordinate center;
  final List<AgapayGoogleMapMarker> markers;
  final AgapayGoogleMapRoute? route;
  final double zoom;
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
    await controller.setBackgroundColor(const Color(0xff00112e));
    await controller.addJavaScriptChannel(
      'AgapayBridge',
      onMessageReceived: _onJavaScriptMessage,
    );
    await controller.setNavigationDelegate(
      NavigationDelegate(
        onPageFinished: (_) {
          _pageLoaded = true;
          _render();
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
    try {
      final values = await Future.wait([
        rootBundle.loadString(_htmlAsset),
        rootBundle.loadString(_demoKeyAsset),
      ]);
      final key = values[1].trim();
      if (key.isEmpty || key == 'PASTE_YOUR_MAPS_DEMO_KEY_HERE') {
        throw const FormatException('Google Maps Demo Key is not configured.');
      }
      _html = values[0];
      _apiKey = key;
      await controller.loadHtmlString(_html!, baseUrl: 'https://agapay.local/');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is FormatException
            ? error.message
            : 'Google Maps Demo Key is not available in this build.';
      });
    }
  }

  void _onJavaScriptMessage(JavaScriptMessage message) {
    try {
      final data = jsonDecode(message.message) as Map<String, dynamic>;
      switch (data['type']) {
        case 'ready':
          if (mounted) {
            setState(() {
              _ready = true;
              _error = null;
            });
          }
        case 'error':
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
    if (controller == null || !_pageLoaded || key == null) return;
    final config = {
      'apiKey': key,
      'center': widget.center.toJson(),
      'zoom': widget.zoom,
      'tilt': widget.tilt,
      'fitAll': widget.fitAll,
      'selectedMarkerId': widget.selectedMarkerId,
      'markers': widget.markers.map((marker) => marker.toJson()).toList(),
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
    'tilt': value.tilt,
    'fitAll': value.fitAll,
    'selectedMarkerId': value.selectedMarkerId,
    'markers': value.markers.map((marker) => marker.toJson()).toList(),
    'route': value.route?.toJson(),
  });

  @override
  void didUpdateWidget(covariant AgapayGoogleMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_signature(widget) == _signature(oldWidget)) return;
    _ready = false;
    _render();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (controller == null) {
      return ColoredBox(
        color: const Color(0xff00112e),
        child: Center(
          child: Semantics(
            label: 'Google map preview',
            child: const Icon(
              Icons.map_outlined,
              color: AppColors.secondary,
              size: 34,
            ),
          ),
        ),
      );
    }
    final error = _error;
    if (error != null) {
      return ColoredBox(
        color: const Color(0xff00112e),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.map_outlined,
                  color: AppColors.secondary,
                  size: 34,
                ),
                const SizedBox(height: 10),
                tx(
                  error,
                  size: 12,
                  color: AppColors.secondary,
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
          const IgnorePointer(
            child: ColoredBox(
              color: Color(0xb800112e),
              child: Center(child: CircularProgressIndicator()),
            ),
          ),
      ],
    );
  }
}
