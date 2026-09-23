import 'package:flutter/material.dart';
import 'app.dart';
import 'controllers/app_controller.dart';
import 'services/firebase_push.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final push = await FirebasePushRuntime.initialize();
  runApp(
    AgapayApp(
      controller: AppController(
        pushTokenProvider: push.provider,
        pushMessages: push.messages,
      ),
    ),
  );
}
