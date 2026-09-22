import 'dart:async';
import 'dart:math' as math;
import 'package:flutter_svg/flutter_svg.dart';
import '../../core/ui.dart';
import '../../navigation/app_routes.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animation = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1800),
  )..repeat();
  Timer? _timer;
  @override
  void initState() {
    super.initState();
    _timer = Timer(const Duration(milliseconds: 2800), () async {
      if (!mounted) return;
      final app = AppScope.of(context);
      await app.restoreSession();
      if (mounted) {
        Navigator.pushReplacementNamed(
          context,
          app.signedIn ? AppRoutes.main : AppRoutes.login,
        );
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _animation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  colors: [
                    AppColors.blue.withValues(alpha: .2),
                    Colors.transparent,
                  ],
                  radius: .65,
                  stops: const [0, .7],
                ),
              ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            height: 120,
            child: Opacity(
              opacity: .15,
              child: SvgPicture.string(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 390 120" preserveAspectRatio="none"><path d="M0,60 C65,20 130,100 195,60 C260,20 325,100 390,60 L390,120 L0,120 Z" fill="#1d4ed8"/></svg>',
                fit: BoxFit.fill,
              ),
            ),
          ),
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Stack(
                  alignment: Alignment.center,
                  children: [
                    AnimatedBuilder(
                      animation: _animation,
                      builder: (context, child) => Transform.scale(
                        scale: 1 + 1.4 * _animation.value,
                        child: Opacity(
                          opacity: .8 * (1 - _animation.value),
                          child: Container(
                            width: 96,
                            height: 96,
                            decoration: BoxDecoration(
                              border: Border.all(color: AppColors.blue),
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                        ),
                      ),
                    ),
                    const AgapayLogo(size: 96),
                  ],
                ),
                const SizedBox(height: 24),
                tx(
                  'AGAPAY',
                  size: 48,
                  weight: 900,
                  display: true,
                  color: Colors.white,
                  spacing: -.96,
                  height: 1,
                ),
                const SizedBox(height: 4),
                tx(
                  'COMMUNITY FLOOD & DISASTER',
                  size: 13,
                  weight: 500,
                  display: true,
                  color: AppColors.link,
                  spacing: 1.3,
                ),
                tx(
                  'EARLY-WARNING SYSTEM',
                  size: 13,
                  weight: 500,
                  display: true,
                  color: AppColors.link,
                  spacing: 1.3,
                ),
                const SizedBox(height: 40),
                AnimatedBuilder(
                  animation: _animation,
                  builder: (context, child) => Row(
                    mainAxisSize: MainAxisSize.min,
                    spacing: 8,
                    children: List.generate(3, (index) {
                      final wave =
                          (math.sin(
                                (_animation.value - index * .14) * 2 * math.pi,
                              ) +
                              1) /
                          2;
                      return Transform.scale(
                        scale: .6 + .4 * wave,
                        child: Opacity(
                          opacity: .4 + .6 * wave,
                          child: const Dot(Color(0xff3b82f6)),
                        ),
                      );
                    }),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
