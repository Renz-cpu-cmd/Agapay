import 'package:geolocator/geolocator.dart';
import 'auth_api.dart';

/// One location fix, requested only after the resident taps the location button.
Future<Position> captureSosLocation() async {
  if (!await Geolocator.isLocationServiceEnabled()) {
    throw const AccountException(
      'Location services are off. Enable them or enter your location manually.',
    );
  }
  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied ||
      permission == LocationPermission.deniedForever) {
    throw const AccountException(
      'Location permission is unavailable. You can still enter your location manually.',
    );
  }
  return Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(
      accuracy: LocationAccuracy.high,
      timeLimit: Duration(seconds: 20),
    ),
  );
}
