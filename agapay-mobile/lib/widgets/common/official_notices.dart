import '../../core/ui.dart';
import '../../models/official_notice.dart';
import '../../models/community_alert.dart';
import '../../controllers/monitoring_controller.dart';

class OfficialNoticesPanel extends StatefulWidget {
  const OfficialNoticesPanel({this.compact = false, super.key});
  final bool compact;
  @override
  State<OfficialNoticesPanel> createState() => _OfficialNoticesPanelState();
}

class _OfficialNoticesPanelState extends State<OfficialNoticesPanel> {
  bool _history = false;
  String? _scope;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final app = AppScope.of(context);
    final scope = '${app.user?.id}:${app.notices.areaId}';
    if (_scope != scope) {
      _scope = scope;
      _history = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), reader = app.notices;
    final feed = _history ? reader.history : reader.current;
    final confirmed = reader.confirmed(feed);
    final now = reader.now();
    final rows = _history
        ? feed.items
        : feed.items
              .where((n) => n.supersededBy == null && now.isBefore(n.expiresAt))
              .toList();
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: tx(
              widget.compact
                  ? 'Latest area advisories'
                  : 'Advisories for your area',
              size: 20,
              weight: 700,
            ),
          ),
          tx(
            'Authority notices and app advisories identify their issuer. Sensor tiers do not issue evacuation orders.',
            color: context.colors.secondary,
          ),
          if (!widget.compact && reader.areaId != null)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ChoiceChip(
                  label: const Text('Current updates'),
                  backgroundColor: context.colors.surface,
                  selectedColor: context.colors.surfaceRaised,
                  labelStyle: TextStyle(color: context.colors.text),
                  checkmarkColor: context.colors.text,
                  side: BorderSide(
                    color: !_history
                        ? context.colors.link
                        : context.colors.border,
                  ),
                  selected: !_history,
                  onSelected: (_) => setState(() => _history = false),
                ),
                ChoiceChip(
                  label: const Text('Notice history'),
                  backgroundColor: context.colors.surface,
                  selectedColor: context.colors.surfaceRaised,
                  labelStyle: TextStyle(color: context.colors.text),
                  checkmarkColor: context.colors.text,
                  side: BorderSide(
                    color: _history
                        ? context.colors.link
                        : context.colors.border,
                  ),
                  selected: _history,
                  onSelected: (_) {
                    setState(() => _history = true);
                    reader.refresh(past: true, offset: 0);
                  },
                ),
                TextButton(
                  onPressed: feed.loading
                      ? null
                      : () => reader.refresh(past: _history),
                  child: const Text('Refresh notices'),
                ),
              ],
            ),
          if (reader.areaId == null)
            const Text(
              'Choose a verified area to see which notices apply. Your profile locality and selected station do not determine this automatically.',
            )
          else ...[
            if (feed.loading) const Text('Checking notice updates…'),
            if (feed.error != null) Text(feed.error!),
            if (feed.checkedAt != null)
              Text(
                '${confirmed ? "Checked" : "LAST KNOWN · updates/cancellations unconfirmed"} · ${MonitoringController.ageLabel(now.difference(feed.checkedAt!).inSeconds.clamp(0, 2147483647))} · ${communityAlertTime(feed.checkedAt!)}',
              ),
            if (!feed.loading && rows.isEmpty)
              Text(
                confirmed
                    ? (_history
                          ? 'No notice history in this scope.'
                          : 'No current notices for this area. This does not establish safety.')
                    : 'Current notices cannot be confirmed.',
              ),
            for (final notice in widget.compact ? rows.take(3) : rows)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: NoticeCard(
                  notice: notice,
                  confirmed: confirmed,
                  now: now,
                ),
              ),
            if (widget.compact) ...[
              if (rows.length > 3 || feed.hasMore)
                const Text(
                  'More notices are available. Open alerts to review every page.',
                ),
              TextButton(
                onPressed: () => app.navigate(AppTab.alerts),
                child: const Text('Read advisories and history'),
              ),
            ] else ...[
              if (_history || feed.hasMore)
                Wrap(
                  spacing: 8,
                  children: [
                    if (_history)
                      TextButton(
                        onPressed: feed.loading || reader.historyOffset == 0
                            ? null
                            : () => reader.refresh(
                                past: true,
                                offset: reader.historyOffset - 50,
                              ),
                        child: const Text('Previous notices'),
                      ),
                    TextButton(
                      onPressed: feed.loading || !feed.hasMore
                          ? null
                          : () {
                              final nextOffset = _history
                                  ? reader.historyOffset + 50
                                  : 0;
                              setState(() => _history = true);
                              reader.refresh(past: true, offset: nextOffset);
                            },
                      child: const Text('More notice history'),
                    ),
                  ],
                ),
            ],
          ],
        ],
      ),
    );
  }
}

class NoticeCard extends StatelessWidget {
  const NoticeCard({
    required this.notice,
    required this.confirmed,
    required this.now,
    super.key,
  });
  final OfficialNotice notice;
  final bool confirmed;
  final DateTime now;
  @override
  Widget build(BuildContext context) {
    final n = notice, lifecycle = n.lifecycle(now);
    final actionable =
        confirmed && lifecycle == 'effective' && n.status == 'Actual';
    final change = n.messageType == 'Cancel'
        ? 'CANCELLED'
        : n.messageType == 'Update'
        ? 'UPDATED'
        : 'ISSUED';
    return Container(
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: context.colors.link, width: 3)),
      ),
      padding: const EdgeInsets.only(left: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '${confirmed ? "" : "LAST KNOWN · "}${n.status == "Actual" ? "" : "${n.status.toUpperCase()} · "}${n.kind} · $lifecycle',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          tx('$change · ${n.headline}', size: 18, weight: 700),
          Text('Issuer: ${n.issuer} (${n.authorityId})'),
          Text('Areas: ${n.areaNames.join(", ")} (${n.areaIds.join(", ")})'),
          Text(
            '${n.severity} severity · ${n.certainty} certainty · ${n.urgency} urgency',
          ),
          const SizedBox(height: 8),
          Text(
            actionable
                ? 'Action from the issuer'
                : 'Recorded instruction · $lifecycle${!confirmed ? "; current updates unconfirmed" : ""}',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          Text(n.instruction),
          Text(
            'Effective ${communityAlertTime(n.effectiveAt)} · Expires ${communityAlertTime(n.expiresAt)}',
          ),
          ExpansionTile(
            key: PageStorageKey('notice-${n.id}-history'),
            tilePadding: EdgeInsets.zero,
            title: const Text('Source and update history'),
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Issued ${communityAlertTime(n.sentAt)} · ${n.messageType} · ${n.id}${n.referenceId == null ? "" : " · References ${n.referenceId}"}${n.supersededBy == null ? "" : " · Replaced by ${n.supersededBy}"}',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
