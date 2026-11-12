import 'package:flutter/material.dart';
import 'app.dart';
import 'controllers/app_controller.dart';
import 'services/firebase_push.dart';
import 'core/release_configuration.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  ReleaseConfiguration.validate();
  final push = await FirebasePushRuntime.initialize();
  final controller = AppController(
    pushTokenProvider: push.provider,
    pushMessages: push.messages,
  );
  await controller.theme.restore();
  runApp(AgapayApp(controller: controller));
}
