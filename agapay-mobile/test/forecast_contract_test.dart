import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agapay_mobile/models/prediction.dart';
import 'package:agapay_mobile/models/forecast_contract.generated.dart';

void main() {
  final cases =
      jsonDecode(
            File(
              '../agapay-docs/contracts/published-forecast-cases.json',
            ).readAsStringSync(),
          )
          as List;
  for (final row in cases) {
    test('OpenAPI shared case: ${row['name']}', () {
      final json = (row['value'] as Map).cast<String, dynamic>();
      if (row['valid'] == true) {
        final value = Prediction.fromPublishedJson(json);
        expect(value.points.first.waterDepthCm, 0);
        expect(value.publication['forecast_id'], json['forecast_id']);
      } else {
        expect(() => Prediction.fromPublishedJson(json), throwsFormatException);
      }
    });
  }
  test('generated Dart contract fingerprint matches checked OpenAPI', () {
    expect(
      sha256
          .convert(
            utf8.encode(
              File(
                '../agapay-docs/contracts/forecasting.openapi.json',
              ).readAsStringSync().replaceAll('\r\n', '\n'),
            ),
          )
          .toString(),
      forecastSchemaSha256,
    );
  });
}
