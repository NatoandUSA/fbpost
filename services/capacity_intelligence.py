"""Read-only capacity intelligence derived from existing operational evidence."""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from repositories.account_repo import AccountRepository
from repositories.activity_repo import ActivityRepository
from repositories.group_repo import GroupRepository
from repositories.moderation_repo import ModerationRepository
from repositories.workflow_repo import WorkflowRepository
from utils import normalize_target_url


def _parse_dt(value):
    if not value:
        return None
    text = str(value).strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _account_state(status: str) -> str:
    low = str(status or '').casefold()
    if any(token in low for token in ('đăng nhập', 'login', 'auth required', 'xác thực')):
        return 'AUTH_REQUIRED'
    if any(token in low for token in ('disabled', 'vô hiệu', 'error', 'lỗi', 'blocked', 'khóa')):
        return 'ERROR'
    return 'READY'


class CapacityIntelligence:
    def __init__(self, profile_capacity):
        self.profile_capacity = profile_capacity

    def _profile_rows(self):
        accounts = AccountRepository().list_accounts()
        perf = {str(row.get('profile_id')): row for row in WorkflowRepository().profile_posting_performance(limit=1000)}
        reserved = set(self.profile_capacity.snapshot().get('reserved_profile_ids') or [])
        cooldown_seconds = max(0, int(os.getenv('FB_PROFILE_COOLDOWN_SECONDS', '0') or 0))
        now = datetime.now(timezone.utc)
        rows = []
        counts = {'READY': 0, 'BUSY': 0, 'COOLDOWN': 0, 'DEGRADED': 0, 'AUTH_REQUIRED': 0, 'ERROR': 0}
        for acc in accounts:
            pid = str(acc.get('id') or acc.get('profile_path_or_id') or '').strip()
            if not pid:
                continue
            p = perf.get(pid, {})
            state = _account_state(acc.get('status'))
            reason = 'account_available'
            last = _parse_dt(p.get('last_activity'))
            if pid in reserved:
                state, reason = 'BUSY', 'reserved_by_active_job'
            elif state == 'READY' and cooldown_seconds > 0 and last and (now-last).total_seconds() < cooldown_seconds:
                state, reason = 'COOLDOWN', 'configured_profile_cooldown'
            elif state == 'READY':
                terminal = int(p.get('published') or 0)+int(p.get('pending') or 0)+int(p.get('unverified') or 0)+int(p.get('failed') or 0)
                rate = float(p.get('published_rate') or 0)
                failures = int(p.get('failed') or 0)
                unverified = int(p.get('unverified') or 0)
                # Quality is advisory only: DEGRADED profiles remain schedulable in P1.3.
                if terminal >= 8 and (rate < 25.0 or failures >= 7 or unverified >= 10):
                    state, reason = 'DEGRADED', 'historical_delivery_quality'
            counts[state] = counts.get(state, 0) + 1
            rows.append({
                'id': pid, 'name': acc.get('name') or pid, 'state': state, 'reason': reason,
                'published_rate': float(p.get('published_rate') or 0),
                'published': int(p.get('published') or 0), 'pending': int(p.get('pending') or 0),
                'unverified': int(p.get('unverified') or 0), 'failed': int(p.get('failed') or 0),
                'membership_unverified': int(p.get('membership_unverified') or 0),
                'avg_seconds': float(p.get('avg_seconds') or 0), 'last_activity': p.get('last_activity'),
            })
        return rows, counts

    def _group_summary(self):
        groups = GroupRepository().list_groups()
        moderated = {normalize_target_url(r.get('group_url') or ''): r for r in ModerationRepository().list_moderated_groups(limit=5000)}
        cooldown_hours = max(1, int(os.getenv('FB_GROUP_COOLDOWN_HOURS', '4') or 4))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
        recent = set()
        for row in ActivityRepository().list_posted_links(limit=5000):
            created = _parse_dt(row.get('created_at'))
            if created and created >= cutoff and str(row.get('publish_state') or '').lower() in {'published','pending','submitted_unverified'}:
                target = normalize_target_url(row.get('target') or '')
                if target:
                    recent.add(target)
        approved_active = 0; pending_blocked = 0; recent_blocked = 0; eligible = 0
        reasons = {}
        approved_targets = []
        eligible_targets = []
        for group in groups:
            if str(group.get('status') or '').lower() != 'approved' or group.get('is_active', True) is False:
                continue
            approved_active += 1
            target = normalize_target_url(group.get('url') or '')
            if target:
                approved_targets.append(target)
            mod = moderated.get(target) or {}
            if int(mod.get('pending_count') or 0) >= int(mod.get('skip_threshold') or 2):
                pending_blocked += 1; reasons[target] = 'PENDING_LIMIT'; continue
            if target in recent:
                recent_blocked += 1; reasons[target] = 'RECENT_POST'; continue
            eligible += 1
            if target:
                eligible_targets.append(target)
        return {
            'groups_total': len(groups), 'groups_approved_active': approved_active,
            'groups_eligible': eligible, 'groups_pending_blocked': pending_blocked,
            'groups_recent_blocked': recent_blocked, 'group_cooldown_hours': cooldown_hours,
            'group_block_reasons': reasons,
            'group_approved_targets': approved_targets,
            'group_eligible_targets': eligible_targets,
        }

    def snapshot(self, worker_snapshot: Dict) -> Dict:
        profiles, profile_counts = self._profile_rows()
        groups = self._group_summary()
        schedulable = profile_counts.get('READY', 0) + profile_counts.get('DEGRADED', 0)
        parallel = min(int(worker_snapshot.get('worker_max') or 1), schedulable, int(groups.get('groups_eligible') or 0))
        durations = [p['avg_seconds'] for p in profiles if p['avg_seconds'] > 0 and p['state'] in {'READY','DEGRADED'}]
        avg_seconds = round(sum(durations)/len(durations), 1) if durations else 0.0
        throughput = round(parallel * 3600.0 / avg_seconds, 1) if parallel and avg_seconds else 0.0
        return {
            **profile_counts,
            'profiles': profiles,
            'profiles_schedulable': schedulable,
            **groups,
            'effective_parallelism': parallel,
            'avg_task_seconds': avg_seconds,
            'estimated_tasks_per_hour': throughput,
            'estimate_basis': 'historical_avg_seconds_x_effective_parallelism',
        }
