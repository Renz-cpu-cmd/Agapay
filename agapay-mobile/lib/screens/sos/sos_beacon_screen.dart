import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../core/utils/formatters.dart';
import '../../models/sos_beacon.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/common/app_buttons.dart';

/// Screen 8: Highly Visible Emergency SOS Beacon
class SosBeaconScreen extends StatefulWidget {
  final AppController controller;

  const SosBeaconScreen({super.key, required this.controller});

  @override
  State<SosBeaconScreen> createState() => _SosBeaconScreenState();
}

class _SosBeaconScreenState extends State<SosBeaconScreen> {
  String _selectedEmergencyType = 'Trapped by floodwaters';

  final List<String> _emergencyTypes = [
    'Trapped by floodwaters',
    'Injured / Medical Emergency',
    'Elderly / Disabled evacuation assistance',
    'Roof / High ground stranded',
  ];

  void _showConfirmationDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: AppColors.alertEvacuate, size: 28),
              SizedBox(width: 10),
              Text(
                'Confirm Emergency SOS',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Are you sure you want to broadcast an emergency SOS beacon to the Barangay Disaster Response team?',
                style: TextStyle(fontSize: 14, color: AppColors.textPrimary, height: 1.4),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.alertEvacuateBg,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'Your real-time GPS coordinates and contact details will be dispatched immediately to rescue personnel.',
                  style: TextStyle(fontSize: 12, color: AppColors.alertEvacuateText),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel', style: TextStyle(color: AppColors.textSecondary, fontWeight: FontWeight.w600)),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(ctx);
                widget.controller.triggerSos(emergencyType: _selectedEmergencyType);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.sosRed,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: const Text('BROADCAST SOS', style: TextStyle(fontWeight: FontWeight.w800)),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final activeSos = widget.controller.activeSos;
        final isSosActive = widget.controller.isSosActive;

        return Scaffold(
          backgroundColor: isSosActive ? const Color(0xFFFFF1F2) : AppColors.background,
          appBar: AppBar(
            backgroundColor: isSosActive ? const Color(0xFFFFF1F2) : Colors.white,
            title: const Text('Emergency SOS'),
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_rounded),
              onPressed: () => Navigator.pop(context),
            ),
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  if (!isSosActive) ...[
                    // Pre-SOS State: Ready to Trigger
                    const SizedBox(height: 10),
                    const Text(
                      'Emergency SOS',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                        color: AppColors.textPrimary,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 16.0),
                      child: Text(
                        'Use SOS only when you or someone nearby is in immediate danger and requires urgent rescue assistance.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 14,
                          color: AppColors.textSecondary,
                          height: 1.4,
                        ),
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Large Pulsing SOS Button
                    Center(
                      child: SOSButton(
                        size: 150,
                        isSending: widget.controller.isSendingSos,
                        onPressed: _showConfirmationDialog,
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Emergency Type Selector
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Emergency Situation Type',
                            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                          ),
                          const SizedBox(height: 10),
                          ..._emergencyTypes.map((type) {
                            return RadioListTile<String>(
                              contentPadding: EdgeInsets.zero,
                              dense: true,
                              title: Text(type, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                              value: type,
                              groupValue: _selectedEmergencyType,
                              activeColor: AppColors.sosRed,
                              onChanged: (val) {
                                if (val != null) setState(() => _selectedEmergencyType = val);
                              },
                            );
                          }),
                        ],
                      ),
                    ),
                  ] else ...[
                    // Active SOS State: Beacon Broadcasting
                    _buildActiveSosDashboard(context, activeSos!),
                  ],

                  const SizedBox(height: 24),

                  // Direct Emergency Hotline Shortcuts
                  _buildEmergencyHotlines(context),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildActiveSosDashboard(BuildContext context, SosBeacon sos) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // SOS Sent Banner
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.sosRed,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: AppColors.sosRed.withOpacity(0.3),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(6),
                        decoration: const BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.sensors_rounded, color: AppColors.sosRed, size: 20),
                      ),
                      const SizedBox(width: 10),
                      const Text(
                        'SOS BEACON ACTIVE',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                  Text(
                    Formatters.formatTimeOnly(sos.timestamp),
                    style: const TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              const Text(
                'Your GPS location is transmitting live to the BDRRMC Disaster Command Center.',
                style: TextStyle(color: Colors.white, fontSize: 13, height: 1.35),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Status Lifecycle Stepper
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Rescue Dispatch Status',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 14),
              _statusStep(
                title: 'SOS Beacon Dispatched',
                subtitle: 'Sent at ${Formatters.formatTimeOnly(sos.timestamp)}',
                isCompleted: true,
                isActive: sos.status == SosStatus.sent,
              ),
              _statusStep(
                title: 'Rescue Unit Assigned',
                subtitle: sos.responderTeam != null
                    ? '${sos.responderTeam} is en route (ETA ~${sos.etaMinutes} mins)'
                    : 'Awaiting responder unit assignment...',
                isCompleted: sos.status == SosStatus.acknowledged || sos.status == SosStatus.resolved,
                isActive: sos.status == SosStatus.acknowledged,
              ),
              _statusStep(
                title: 'Resident Evacuated / Safe',
                subtitle: 'Rescue completed & marked safe',
                isCompleted: sos.status == SosStatus.resolved,
                isActive: sos.status == SosStatus.resolved,
                isLast: true,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Transmitted GPS Details
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: [
              _detailRow('Beacon ID', sos.id),
              const Divider(height: 16),
              _detailRow('Resident Name', sos.userName),
              const Divider(height: 16),
              _detailRow('Contact Number', sos.phone),
              const Divider(height: 16),
              _detailRow('Barangay Zone', sos.barangay),
              const Divider(height: 16),
              _detailRow('GPS Coordinates', '${sos.latitude.toStringAsFixed(4)}° N, ${sos.longitude.toStringAsFixed(4)}° E'),
              const Divider(height: 16),
              _detailRow('Reported Situation', sos.emergencyType ?? 'Flood danger'),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // Cancel / Resolve Actions
        Row(
          children: [
            Expanded(
              child: SecondaryButton(
                label: 'Cancel SOS',
                onPressed: () {
                  widget.controller.cancelSos();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('SOS beacon cancelled.')),
                  );
                },
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                onPressed: () {
                  widget.controller.resolveSos();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Glad you are safe! Emergency beacon marked resolved.'),
                      backgroundColor: AppColors.alertNormal,
                    ),
                  );
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.alertNormal,
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 50),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('I am Safe', style: TextStyle(fontWeight: FontWeight.w700)),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _statusStep({
    required String title,
    required String subtitle,
    required bool isCompleted,
    required bool isActive,
    bool isLast = false,
  }) {
    Color iconBg = AppColors.surfaceSecondary;
    Color iconColor = AppColors.textMuted;

    if (isActive) {
      iconBg = AppColors.sosRedLight;
      iconColor = AppColors.sosRed;
    } else if (isCompleted) {
      iconBg = AppColors.alertNormalBg;
      iconColor = AppColors.alertNormal;
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(color: iconBg, shape: BoxShape.circle),
              child: Icon(
                isCompleted ? Icons.check_rounded : (isActive ? Icons.autorenew_rounded : Icons.circle_outlined),
                size: 16,
                color: iconColor,
              ),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 32,
                color: isCompleted ? AppColors.alertNormal : AppColors.border,
              ),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: isCompleted || isActive ? AppColors.textPrimary : AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
              ),
              if (!isLast) const SizedBox(height: 12),
            ],
          ),
        ),
      ],
    );
  }

  Widget _detailRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
        Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
      ],
    );
  }

  Widget _buildEmergencyHotlines(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Emergency Hotline Quick-Dial',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
          ),
          const SizedBox(height: 10),
          _hotlineTile('National Emergency Hotline', AppConstants.hotlineNationalEmergency, Icons.emergency_rounded),
          _hotlineTile('NDRRMC Operations Center', AppConstants.hotlineNDRRMC, Icons.shield_rounded),
          _hotlineTile('Philippine Red Cross', AppConstants.hotlineRedCross, Icons.healing_rounded),
          _hotlineTile('Local BDRRMC Command Desk', AppConstants.hotlineLocalBDRRMC, Icons.phone_in_talk_rounded),
        ],
      ),
    );
  }

  Widget _hotlineTile(String name, String number, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: AppColors.secondary),
              const SizedBox(width: 8),
              Text(name, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary)),
            ],
          ),
          Text(
            number,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppColors.primary),
          ),
        ],
      ),
    );
  }
}
