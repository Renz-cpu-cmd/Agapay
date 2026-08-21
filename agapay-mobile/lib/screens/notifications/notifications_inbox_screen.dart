import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/notification_item.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/cards/notification_card.dart';
import '../../widgets/common/state_views.dart';
import '../../navigation/app_routes.dart';

/// Screen 11: Notifications Inbox & Alert History
class NotificationsInboxScreen extends StatefulWidget {
  final AppController controller;

  const NotificationsInboxScreen({super.key, required this.controller});

  @override
  State<NotificationsInboxScreen> createState() => _NotificationsInboxScreenState();
}

class _NotificationsInboxScreenState extends State<NotificationsInboxScreen> {
  int _selectedFilterIndex = 0; // 0: All, 1: Alerts, 2: System

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final allNotifs = widget.controller.notifications;
        final filteredNotifs = allNotifs.where((n) {
          if (_selectedFilterIndex == 1) {
            return n.type == NotificationType.floodAlert ||
                n.type == NotificationType.waterLevelWarning ||
                n.type == NotificationType.evacuationOrder;
          } else if (_selectedFilterIndex == 2) {
            return n.type == NotificationType.systemStatus || n.type == NotificationType.weatherUpdate;
          }
          return true;
        }).toList();

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            title: const Text('Notifications'),
            actions: [
              if (allNotifs.isNotEmpty)
                TextButton(
                  onPressed: widget.controller.markAllNotificationsRead,
                  child: const Text('Mark All Read', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
            ],
          ),
          body: SafeArea(
            child: Column(
              children: [
                // Filter Tabs
                Container(
                  color: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      _tabChip(0, 'All (${allNotifs.length})'),
                      const SizedBox(width: 8),
                      _tabChip(1, 'Flood Alerts'),
                      const SizedBox(width: 8),
                      _tabChip(2, 'System & Weather'),
                    ],
                  ),
                ),
                const Divider(height: 1, color: AppColors.border),

                // Notifications List or Empty State
                Expanded(
                  child: filteredNotifs.isEmpty
                      ? const EmptyState(
                          title: 'No Notifications',
                          message: 'You are all caught up. New flood warnings and system bulletins will appear here.',
                          icon: Icons.notifications_off_outlined,
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.all(16),
                          itemCount: filteredNotifs.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 10),
                          itemBuilder: (context, index) {
                            final notif = filteredNotifs[index];
                            return NotificationCard(
                              notification: notif,
                              onTap: () {
                                widget.controller.markNotificationRead(notif.id);
                                if (notif.relatedStationId != null) {
                                  widget.controller.selectStation(notif.relatedStationId!);
                                  Navigator.pushNamed(context, AppRoutes.waterLevelDetails);
                                }
                              },
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _tabChip(int index, String label) {
    final isSelected = _selectedFilterIndex == index;
    return ChoiceChip(
      selected: isSelected,
      label: Text(label),
      selectedColor: AppColors.primary,
      backgroundColor: AppColors.surfaceSecondary,
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        color: isSelected ? Colors.white : AppColors.textSecondary,
      ),
      side: BorderSide(color: isSelected ? AppColors.primary : AppColors.border),
      onSelected: (val) {
        if (val) setState(() => _selectedFilterIndex = index);
      },
    );
  }
}
