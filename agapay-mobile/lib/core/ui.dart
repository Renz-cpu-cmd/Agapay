import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'theme/app_theme.dart';
export 'package:flutter/material.dart';
export 'theme/app_theme.dart';
export '../controllers/app_controller.dart';
export '../models/alert_level.dart';

Text tx(
  String value, {
  double size = 14,
  Color color = AppColors.text,
  int weight = 400,
  bool display = false,
  bool mono = false,
  double? height,
  double spacing = 0,
  TextAlign? align,
  int? lines,
}) => Text(
  value,
  textAlign: align,
  maxLines: lines,
  overflow: lines == null ? null : TextOverflow.ellipsis,
  style: TextStyle(
    fontFamily: mono
        ? 'JetBrainsMono'
        : display
        ? 'Outfit'
        : 'Inter',
    fontSize: size,
    // The bundled variable fonts set weight through their wght axis. Avoid
    // synthetic bold on top of that axis when an asset is registered as 400.
    fontWeight: FontWeight.w400,
    fontVariations: [FontVariation('wght', weight.toDouble())],
    color: color,
    height: height ?? 1.5,
    letterSpacing: spacing,
  ),
);

Widget caption(String value) => tx(
  value,
  size: 10,
  color: AppColors.muted,
  mono: true,
  weight: 600,
  spacing: 1,
);
const gap = SizedBox(height: 12);

class Panel extends StatelessWidget {
  const Panel({
    required this.child,
    this.padding = 16,
    this.radius = 16,
    this.color = AppColors.surface,
    this.border = AppColors.border,
    super.key,
  });
  final Widget child;
  final double padding, radius;
  final Color color, border;
  @override
  Widget build(BuildContext context) {
    final useDefaultSurface = color == AppColors.surface;
    return Container(
      padding: EdgeInsets.all(padding),
      decoration: BoxDecoration(
        color: useDefaultSurface ? null : color,
        gradient: useDefaultSurface
            ? const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppColors.surfaceRaised, AppColors.surface],
              )
            : null,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: border),
        boxShadow: const [
          BoxShadow(
            color: Color(0x26000000),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }
}

class PageContent extends StatelessWidget {
  const PageContent({
    required this.children,
    this.padding = const EdgeInsets.fromLTRB(16, 16, 16, 20),
    super.key,
  });
  final List<Widget> children;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
    padding: padding,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  );
}

class PageHeading extends StatelessWidget {
  const PageHeading(
    this.title,
    this.subtitle, {
    this.onBack,
    this.subtitleColor = AppColors.muted,
    super.key,
  });
  final String title, subtitle;
  final VoidCallback? onBack;
  final Color subtitleColor;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 18),
    child: Row(
      children: [
        if (onBack != null) ...[
          Semantics(
            label: 'Back',
            button: true,
            child: InkWell(
              onTap: onBack,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  border: Border.all(color: AppColors.border),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Center(
                  child: SvgIcon('back', size: 18, color: AppColors.secondary),
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              tx(
                title,
                size: 24,
                weight: 700,
                display: true,
                color: Colors.white,
              ),
              tx(subtitle, size: 11, mono: true, color: subtitleColor),
            ],
          ),
        ),
      ],
    ),
  );
}

class ActionButton extends StatelessWidget {
  const ActionButton(
    this.label, {
    required this.onPressed,
    this.color = AppColors.blue,
    this.endColor,
    this.textColor = Colors.white,
    this.border,
    this.vertical = 16,
    this.fontSize = 14,
    this.weight = 700,
    this.glow = false,
    super.key,
  });
  final String label;
  final VoidCallback? onPressed;
  final Color color, textColor;
  final Color? endColor, border;
  final double vertical, fontSize;
  final int weight;
  final bool glow;
  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    enabled: onPressed != null,
    child: Opacity(
      opacity: onPressed == null ? .7 : 1,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: endColor == null ? color : null,
          gradient: endColor == null
              ? null
              : LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [color, endColor!],
                ),
          border: border == null ? null : Border.all(color: border!),
          borderRadius: BorderRadius.circular(12),
          boxShadow: glow
              ? [
                  BoxShadow(
                    color: color.withValues(alpha: .25),
                    blurRadius: 20,
                    offset: const Offset(0, 4),
                  ),
                ]
              : null,
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: onPressed,
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: 10, vertical: vertical),
              child: Center(
                child: tx(
                  label,
                  size: fontSize,
                  weight: weight,
                  display: true,
                  color: textColor,
                  spacing: .7,
                  align: TextAlign.center,
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class Dot extends StatelessWidget {
  const Dot(this.color, {this.size = 8, this.glow = false, super.key});
  final Color color;
  final double size;
  final bool glow;
  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      color: color,
      shape: BoxShape.circle,
      boxShadow: glow ? [BoxShadow(color: color, blurRadius: 8)] : null,
    ),
  );
}

/// Exact path data from the supplied React SVGs.
class SvgIcon extends StatelessWidget {
  const SvgIcon(
    this.name, {
    this.size = 22,
    this.color = AppColors.secondary,
    super.key,
  });
  final String name;
  final double size;
  final Color color;
  static const paths = {
    'back': '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    'arrow': '<path d="M5 12h14M12 5l7 7-7 7"/>',
    'chevron': '<path d="M9 18l6-6-6-6"/>',
    'down': '<path d="M6 9l6 6 6-6"/>',
    'home':
        '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    'map':
        '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>',
    'sos':
        '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    'bell':
        '<path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>',
    'user':
        '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    'check': '<polyline points="20 6 9 17 4 12"/>',
  };
  @override
  Widget build(BuildContext context) => SvgPicture.string(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="${name == 'back' ? 2.5 : 1.8}" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>',
    width: size,
    height: size,
    colorFilter: ColorFilter.mode(color, BlendMode.srcIn),
  );
}

class AgapayLogo extends StatelessWidget {
  const AgapayLogo({this.size = 64, super.key});

  final double size;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: size,
    height: size,
    child: ClipOval(
      child: Image.asset(
        'assets/images/agapay-logo.png',
        width: size,
        height: size,
        fit: BoxFit.contain,
        filterQuality: FilterQuality.high,
        semanticLabel: 'AGAPAY logo',
      ),
    ),
  );
}

void previewNotice(BuildContext context, String message) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
}

class DataRow extends StatelessWidget {
  const DataRow(
    this.label,
    this.value, {
    this.color = AppColors.text,
    this.mono = false,
    super.key,
  });
  final String label, value;
  final Color color;
  final bool mono;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Row(
      children: [
        tx(label, size: 11, color: AppColors.muted, display: true),
        const SizedBox(width: 12),
        Expanded(
          child: tx(
            value,
            size: 12,
            color: color,
            display: !mono,
            mono: mono,
            weight: mono ? 400 : 600,
            align: TextAlign.right,
          ),
        ),
      ],
    ),
  );
}
