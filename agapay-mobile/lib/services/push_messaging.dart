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

abstract interface class PushMessages {
  Stream<Map<String, Object?>> get foreground;
  Stream<Map<String, Object?>> get opened;
  Future<Map<String, Object?>?> initialMessage();
}
