import '../core/operational_vocabulary.dart';

class OfficialNotice {
  OfficialNotice.fromJson(Map<String, dynamic> json)
    : id = json['id'] as String,
      issuer = json['issuer_name'] as String,
      authorityId = json['authority_id'] as String,
      authorityClass = json['authority_class'] as String,
      headline = json['headline'] as String,
      instruction = json['instruction'] as String,
      status = json['status'] as String,
      category = json['category'] as String,
      messageType = json['message_type'] as String,
      referenceId = json['reference_id'] as String?,
      supersededBy = json['superseded_by'] as String?,
      areaIds = List<String>.from(json['area_ids'] as List),
      areaNames = List<String>.from(json['area_names'] as List),
      urgency = json['urgency'] as String,
      severity = json['severity'] as String,
      certainty = json['certainty'] as String,
      sentAt = DateTime.parse(json['sent_at'] as String),
      effectiveAt = DateTime.parse(json['effective_at'] as String),
      expiresAt = DateTime.parse(json['expires_at'] as String) {
    if (!['app_operator', 'public_authority'].contains(authorityClass) ||
        !['Actual', 'Exercise', 'Test'].contains(status) ||
        !['Alert', 'Update', 'Cancel'].contains(messageType) ||
        areaIds.isEmpty ||
        areaIds.length != areaNames.length) {
      throw const FormatException('Incomplete issuer or notice lifecycle');
    }
  }
  final String id, issuer, authorityId, authorityClass, headline, instruction;
  final String status, category, messageType, urgency, severity, certainty;
  final String? referenceId, supersededBy;
  final List<String> areaIds, areaNames;
  final DateTime sentAt, effectiveAt, expiresAt;
  String get kind => authorityClass == 'app_operator'
      ? 'App advisory'
      : category == 'action'
      ? 'Authority-issued action'
      : OperationalVocabulary.officialAdvisory;
  String lifecycle(DateTime now) => supersededBy != null
      ? 'superseded'
      : messageType == 'Cancel'
      ? 'cancelled'
      : !now.isBefore(expiresAt)
      ? 'expired'
      : now.isBefore(effectiveAt)
      ? 'scheduled'
      : 'effective';
}
