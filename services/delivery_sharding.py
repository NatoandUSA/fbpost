"""Capacity-aware sharding of approved publication queue items into execution jobs."""
from __future__ import annotations

import hashlib
import threading
from typing import Dict, List

from repositories.campaign_repo import CampaignRepository
from services.capacity_intelligence import CapacityIntelligence
from utils import normalize_target_url


_DISPATCH_LOCK = threading.Lock()


class DeliveryShardingPlanner:
    def __init__(self, job_manager):
        self.job_manager = job_manager

    @staticmethod
    def _profile_rank(profile: dict):
        state_rank = {'READY': 0, 'DEGRADED': 1}
        return (
            state_rank.get(str(profile.get('state') or ''), 9),
            -float(profile.get('published_rate') or 0),
            int(profile.get('failed') or 0),
            int(profile.get('unverified') or 0),
            str(profile.get('last_activity') or ''),
            str(profile.get('id') or ''),
        )

    @staticmethod
    def _shard_id(campaign_id: str, profile_id: str, item_ids: List[str]) -> str:
        raw = f"{campaign_id}|{profile_id}|{'|'.join(item_ids)}"
        return 'shard-' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]

    def plan(self, campaign_id: str, *, batch_size: int = 10, max_shards: int | None = None, queue_item_ids: List[str] | None = None) -> Dict:
        batch_size = max(8, min(int(batch_size or 10), 12))
        capacity = self.job_manager.full_capacity_snapshot()
        effective = int(capacity.get('effective_parallelism') or 0)
        if max_shards is not None:
            effective = min(effective, max(0, int(max_shards)))

        active_shard_jobs = []
        active_item_ids = set()
        active_profile_ids = set()
        for job in self.job_manager.list_jobs(limit=1000):
            if str(job.get('state') or '') not in {'queued', 'running'}:
                continue
            payload = job.get('payload') or {}
            if not str(payload.get('shardId') or '').strip():
                continue
            active_shard_jobs.append(job)
            for profile_id in payload.get('accountIds') or []:
                if str(profile_id).strip():
                    active_profile_ids.add(str(profile_id).strip())
            for task in payload.get('tasks') or []:
                if isinstance(task, dict) and str(task.get('queueItemId') or '').strip():
                    active_item_ids.add(str(task.get('queueItemId')).strip())

        profiles = [p for p in (capacity.get('profiles') or [])
                    if p.get('state') in {'READY', 'DEGRADED'} and str(p.get('id') or '') not in active_profile_ids]
        profiles = sorted(profiles, key=self._profile_rank)
        shard_slots = min(effective, len(profiles))

        all_items = [i for i in CampaignRepository().list_queue()
                     if str(i.get('campaign_id') or '') == str(campaign_id)
                     and str(i.get('state') or '').lower() == 'approved']
        requested_item_ids = None
        missing_requested_item_ids = []
        if queue_item_ids is not None:
            requested_item_ids = []
            seen_requested = set()
            for raw_id in queue_item_ids:
                item_id = str(raw_id or '').strip()
                if item_id and item_id not in seen_requested:
                    requested_item_ids.append(item_id)
                    seen_requested.add(item_id)
            by_id = {str(item.get('id') or ''): item for item in all_items}
            items = [by_id[item_id] for item_id in requested_item_ids if item_id in by_id]
            missing_requested_item_ids = [item_id for item_id in requested_item_ids if item_id not in by_id]
        else:
            items = all_items
        blocked = {normalize_target_url(k): v for k, v in (capacity.get('group_block_reasons') or {}).items() if normalize_target_url(k)}
        approved_targets = {normalize_target_url(t) for t in (capacity.get('group_approved_targets') or []) if normalize_target_url(t)}
        eligible_targets = {normalize_target_url(t) for t in (capacity.get('group_eligible_targets') or []) if normalize_target_url(t)}
        seen_targets = set()
        eligible = []
        skipped = [{'id': item_id, 'reason': 'REQUESTED_ITEM_NOT_APPROVED'} for item_id in missing_requested_item_ids]
        for item in items:
            if str(item.get('id') or '') in active_item_ids:
                skipped.append({'id': item.get('id'), 'reason': 'ALREADY_IN_FLIGHT'})
                continue
            target = normalize_target_url(item.get('target') or '')
            if not target:
                skipped.append({'id': item.get('id'), 'reason': 'INVALID_TARGET'})
                continue
            if target in seen_targets:
                skipped.append({'id': item.get('id'), 'reason': 'DUPLICATE_TARGET_IN_CAMPAIGN'})
                continue
            seen_targets.add(target)
            if target not in approved_targets:
                skipped.append({'id': item.get('id'), 'target': target, 'reason': 'GROUP_NOT_APPROVED_ACTIVE'})
                continue
            reason = blocked.get(target)
            if reason:
                skipped.append({'id': item.get('id'), 'target': target, 'reason': reason})
                continue
            if target not in eligible_targets:
                skipped.append({'id': item.get('id'), 'target': target, 'reason': 'GROUP_NOT_ELIGIBLE'})
                continue
            eligible.append(item)

        wave_limit = shard_slots * batch_size
        wave_items = eligible[:wave_limit] if wave_limit > 0 else []
        shards = []
        for index in range(shard_slots):
            chunk = wave_items[index * batch_size:(index + 1) * batch_size]
            if not chunk:
                break
            profile = profiles[index]
            tasks = []
            for item in chunk:
                task = {
                    'target': item.get('target') or '',
                    'content': item.get('content') or '',
                    'queueItemId': item.get('id'),
                }
                tasks.append(task)
            item_ids = [str(i.get('id') or '') for i in chunk]
            shards.append({
                'shardId': self._shard_id(campaign_id, str(profile.get('id')), item_ids),
                'campaignId': campaign_id,
                'profileId': profile.get('id'),
                'profileName': profile.get('name'),
                'profileState': profile.get('state'),
                'taskCount': len(tasks),
                'tasks': tasks,
            })

        return {
            'campaign_id': campaign_id,
            'batch_size': batch_size,
            'effective_parallelism': effective,
            'shard_slots': shard_slots,
            'active_shard_jobs': len(active_shard_jobs),
            'active_shard_item_ids': sorted(active_item_ids),
            'active_shard_profile_ids': sorted(active_profile_ids),
            'approved_items': len(all_items),
            'selected_approved_items': len(items),
            'requested_item_ids': requested_item_ids,
            'eligible_items': len(eligible),
            'wave_items': len(wave_items),
            'remaining_after_wave': max(0, len(eligible) - len(wave_items)),
            'skipped': skipped,
            'shards': shards,
            'capacity': {
                'worker_max': capacity.get('worker_max'),
                'profiles_schedulable': capacity.get('profiles_schedulable'),
                'groups_eligible': capacity.get('groups_eligible'),
            },
        }

    def dispatch(self, campaign_id: str, *, batch_size: int = 10, max_shards: int | None = None, base_payload: dict | None = None, queue_item_ids: List[str] | None = None) -> Dict:
        with _DISPATCH_LOCK:
            plan = self.plan(campaign_id, batch_size=batch_size, max_shards=max_shards, queue_item_ids=queue_item_ids)
            base = dict(base_payload or {})
            active_shards = set()
            for job in self.job_manager.list_jobs(limit=1000):
                if str(job.get('state') or '') not in {'queued', 'running'}:
                    continue
                payload = job.get('payload') or {}
                shard_id = str(payload.get('shardId') or '').strip()
                if shard_id:
                    active_shards.add(shard_id)
            jobs = []
            skipped_active = []
            for shard in plan['shards']:
                if shard['shardId'] in active_shards:
                    skipped_active.append(shard['shardId'])
                    continue
                profile_id = str(shard['profileId'])
                payload = {
                    **base,
                    'command': 'group',
                    'campaignId': campaign_id,
                    'shardId': shard['shardId'],
                    'rotateAccounts': True,
                    'accountIds': [profile_id],
                    'tasks': shard['tasks'],
                }
                job_id = self.job_manager.submit_job('group', payload, account_id=profile_id)
                jobs.append({
                    'job_id': job_id,
                    'shard_id': shard['shardId'],
                    'profile_id': profile_id,
                    'profile_name': shard['profileName'],
                    'task_count': shard['taskCount'],
                })
            return {**plan, 'dispatched_jobs': jobs, 'dispatched_shards': len(jobs), 'skipped_active_shards': skipped_active}
