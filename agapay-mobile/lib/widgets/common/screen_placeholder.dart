import 'package:flutter/material.dart';

/// Temporary content while the corresponding Figma screen is being prepared.
class ScreenPlaceholder extends StatelessWidget {
  const ScreenPlaceholder({
    required this.title,
    required this.sections,
    this.actions = const [],
    super.key,
  });

  final String title;
  final List<String> sections;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(title, style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 12),
        const Text('Frontend placeholder — Figma design pending'),
        const SizedBox(height: 24),
        for (final section in sections)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(section),
          ),
        ...actions,
      ],
    ),
  );
}
