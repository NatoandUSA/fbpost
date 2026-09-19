"""Auto-refill / backpressure controller for sharded campaign delivery."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List

from repositories.campaign_repo import CampaignRepository
from services.delivery_sharding import DeliveryShardingPlanner


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class AutoRefillController:
    def __init__(self, job_manager, *, interval_seconds=None, queue_multiplier=None):
        self.job_manager = job_manager
        self.interval_seconds = max(5, int(interval_seconds or os.getenv('FB_AUTO_REFILL_INTERVAL_SECONDS', '15') or 15))
        self.queue_multiplier = max(1, min(int(queue_multiplier or os.getenv('FB_AUTO_REFILL_QUEUE_MULTIPLIER', '1') or 1), 3))
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._last_result = None
        self._last_error = None
        self._last_tick_at = None
        self._cursor = 0

    def _active_campaigns_with_approved_items(self) -> List[dict]:
        campaigns = [c for c in CampaignRepository().list_campaigns()
                     if str(c.get('state') or c.get('status') or 'active').lower() == 'active']
        approved_counts = {}
        for item in CampaignRepository().list_queue():
            if str(item.get('state') or '').lower() != 'approved':
                continue
            cid = str(item.get('campaign_id') or '').strip()
            if cid:
                approved_counts[cid] = approved_counts.get(cid, 0) + 1
        return [c for c in campaigns if approved_counts.get(str(c.get('id') or ''), 0) > 0]

    def status(self) -> Dict:
        thread = self._thread
        return {
            'enabled': bool(thread and thread.is_alive()),
            'interval_seconds': self.interval_seconds,
            'queue_multiplier': self.queue_multiplier,
            'last_tick_at': self._last_tick_at,
            'last_error': self._last_error,
            'last_result': self._last_result,
        }

    def tick(self, *, batch_size=10) -> Dict:
        with self._lock:
            self._last_tick_at = _now_iso()
            capacity = self.job_manager.full_capacity_snapshot()
            worker_max = max(1, int(capacity.get('worker_max') or 1))
            worker_active = max(0, int(capacity.get('worker_active') or 0))
            queue_depth = max(0, int(capacity.get('queue_depth') or 0))
            max_inflight = worker_max * self.queue_multiplier
            inflight = worker_active + queue_depth
            budget = max(0, max_inflight - inflight)

            campaigns = self._active_campaigns_with_approved_items()
            if not campaigns:
                result = {
                    'decision': 'DRAINED', 'reason': 'NO_ACTIVE_CAMPAIGN_WITH_APPROVED_ITEMS',
                    'budget': budget, 'inflight': inflight, 'max_inflight': max_inflight,
                    'campaigns_considered': 0, 'dispatched_shards': 0,
                }
                self._last_result = result; self._last_error = None; return result
            if budget <= 0:
                result = {
                    'decision': 'WAIT', 'reason': 'BACKPRESSURE_LIMIT_REACHED',
                    'budget': 0, 'inflight': inflight, 'max_inflight': max_inflight,
                    'campaigns_considered': len(campaigns), 'dispatched_shards': 0,
                }
                self._last_result = result; self._last_error = None; return result

            # Fair round-robin across campaigns; one controller tick can refill several
            # campaigns, but never above the global in-flight budget.
            n = len(campaigns)
            ordered = campaigns[self._cursor % n:] + campaigns[:self._cursor % n]
            dispatched = []
            blocked = []
            remaining_budget = budget
            for campaign in ordered:
                if remaining_budget <= 0:
                    break
                cid = str(campaign.get('id') or '')
                base_payload = {'brandKey': campaign.get('brand')} if campaign.get('brand') else {}
                result = DeliveryShardingPlanner(self.job_manager).dispatch(
                    cid, batch_size=batch_size, max_shards=remaining_budget, base_payload=base_payload
                )
                count = int(result.get('dispatched_shards') or 0)
                if count:
                    dispatched.append({
                        'campaign_id': cid, 'campaign_name': campaign.get('name'),
                        'dispatched_shards': count, 'remaining_after_wave': result.get('remaining_after_wave', 0),
                        'jobs': result.get('dispatched_jobs') or [],
                    })
                    remaining_budget -= count
                else:
                    blocked.append({
                        'campaign_id': cid, 'campaign_name': campaign.get('name'),
                        'approved_items': result.get('approved_items', 0),
                        'eligible_items': result.get('eligible_items', 0),
                        'skipped': result.get('skipped') or [],
                    })
            self._cursor = (self._cursor + 1) % max(1, n)
            total = sum(x['dispatched_shards'] for x in dispatched)
            if total:
                decision, reason = 'REFILL', 'CAPACITY_AVAILABLE'
            else:
                decision, reason = 'BLOCKED', 'NO_ELIGIBLE_SHARD_CAPACITY'
            result = {
                'decision': decision, 'reason': reason,
                'budget': budget, 'remaining_budget': remaining_budget,
                'inflight': inflight, 'max_inflight': max_inflight,
                'campaigns_considered': len(campaigns),
                'dispatched_shards': total,
                'dispatched': dispatched,
                'blocked': blocked,
            }
            self._last_result = result; self._last_error = None
            return result

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self.tick()
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)[:300]
            self._stop_event.wait(self.interval_seconds)

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name='fb-auto-refill', daemon=True)
            self._thread.start()
            return True

    def stop(self) -> bool:
        thread = self._thread
        if not thread or not thread.is_alive():
            return False
        self._stop_event.set()
        thread.join(timeout=min(2.0, float(self.interval_seconds)))
        return True
