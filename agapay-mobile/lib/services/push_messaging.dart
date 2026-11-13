/// Push data selects an episode only. FastAPI remains the source of its contents.
class SensorPush {
  const SensorPush(this.alertId);
  final int alertId;

  static SensorPush? parse(Map<String, Object?> data) {
    final value = data['alert_id'];
    if (data['type'] != 'SENSOR_ESCALATION' ||
        value is! String ||
        !RegExp(r'^[1-9][0-9]{0,14}$').hasMatch(value)) {
      return null;
    }
    final id = int.tryParse(value);
    return id == null ? null : SensorPush(id);
  }
}

const exerciseAlertTitle = 'AGAPAY TEST ALERT — NOT A REAL EMERGENCY';

/// EXERCISE_TEST drill push. Never an operational episode: it opens a local
/// test-only view and is never added to community alert history or receipts.
class ExercisePush {
  const ExercisePush(this.deliveryId, this.sessionId);
  final String deliveryId, sessionId;
  static final _uuid = RegExp(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
  );

  static ExercisePush? parse(Map<String, Object?> data) {
    final delivery = data['delivery_id'], session = data['session_id'];
    if (data['type'] != 'EXERCISE_TEST' ||
        data['exercise'] != 'true' ||
        delivery is! String ||
        session is! String ||
        !_uuid.hasMatch(delivery) ||
        !_uuid.hasMatch(session)) {
      return null;
    }
    return ExercisePush(delivery, session);
  }
}

abstract interface class PushMessages {
  Stream<Map<String, Object?>> get foreground;
  Stream<Map<String, Object?>> get opened;
  Future<Map<String, Object?>?> initialMessage();
}
