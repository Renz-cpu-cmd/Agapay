import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../branding/agapay_logo.dart';

/// Top Application Header with AGAPAY Logo, Barangay Pill, and Notification Bell
class AppHeader extends StatelessWidget implements PreferredSizeWidget {
  final String barangay;
  final int unreadCount;
  final bool isOffline;
  final VoidCallback? onNotificationTap;
  final VoidCallback? onBarangayTap;

  const AppHeader({
    super.key,
    required this.barangay,
    this.unreadCount = 0,
    this.isOffline = false,
    this.onNotificationTap,
    this.onBarangayTap,
  });

  @override
  Size get preferredSize => const Size.fromHeight(60);

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: SafeArea(
        bottom: false,
        child: Row(
          children: [
            // AGAPAY Brand Icon & Title
            Row(
              children: [
                const AgapayLogo(size: 34),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'AGAPAY',
                      style: TextStyle(
                        color: AppColors.primary,
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.5,
                        height: 1.1,
                      ),
                    ),
                    Text(
                      'EARLY WARNING',
                      style: TextStyle(
                        color: AppColors.secondary.withOpacity(0.9),
                        fontSize: 8.5,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const Spacer(),
            // Barangay Location Badge
            InkWell(
              borderRadius: BorderRadius.circular(20),
              onTap: onBarangayTap,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: AppColors.surfaceSecondary,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.border),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isOffline ? Icons.cloud_off_rounded : Icons.location_on_rounded,
                      size: 13,
                      color: isOffline ? AppColors.offlineGrey : AppColors.secondary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      barangay.replaceAll('Brgy. ', ''),
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Notification Bell with Badge
            IconButton(
              icon: Stack(
                clipBehavior: Clip.none,
                children: [
                  const Icon(Icons.notifications_outlined, color: AppColors.textPrimary, size: 24),
                  if (unreadCount > 0)
                    Positioned(
                      right: -2,
                      top: -2,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: const BoxDecoration(
                          color: AppColors.alertEvacuate,
                          shape: BoxShape.circle,
                        ),
                        child: Text(
                          '$unreadCount',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 9,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              onPressed: onNotificationTap,
              tooltip: 'Notifications',
            ),
          ],
        ),
      ),
    );
  }
}
