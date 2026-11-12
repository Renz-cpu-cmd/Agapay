/// Display labels only; never change wire enums or SOS receipt states here.
abstract final class OperationalVocabulary {
  static const observed = 'Observed';
  static const lastKnown = 'Last known';
  static const noValidReading = 'No valid reading';
  static const experimentalProjection = 'Experimental projection';
  static const officialAdvisory = 'Official advisory';
  static const practiceSos = 'SOS';

  static String sourceStatusLabel(
    String status, {
    double? value,
    bool current = false,
    DateTime? measuredAt,
  }) => switch (status) {
    'LIVE' ||
    'STALE READING' ||
    'WAITING FOR DATA' => readingLabel(value, current, measuredAt),
    _ => status,
  };

  static String readingLabel(
    double? value,
    bool current,
    DateTime? measuredAt,
  ) => value == null
      ? noValidReading
      : current && measuredAt != null
      ? observed
      : lastKnown;
}
