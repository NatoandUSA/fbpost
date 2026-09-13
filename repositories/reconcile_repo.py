import uuid
from datetime import datetime, timezone, timedelta
from repositories.base import BaseRepository

def _now(): return datetime.now(timezone.utc)
def _iso(dt): return dt.isoformat(timespec="seconds")

class ReconcileRepository(BaseRepository):
    DELAYS=(30,120,600)
    MODERATION_DELAYS=(600,1800,7200,21600,43200,86400)
    def enqueue(self,target_url,content,account_id=None,queue_item_id=None,delay_seconds=30,reconcile_kind='uncertain'):
        now=_now(); rid=uuid.uuid4().hex
        with self.transaction() as conn:
            existing=conn.execute("SELECT id FROM reconciliation_queue WHERE target_url=? AND COALESCE(account_id,'')=COALESCE(?,'') AND content=? AND status IN ('pending','running') LIMIT 1",(target_url,account_id,content)).fetchone()
            if existing: return existing["id"]
            conn.execute("INSERT INTO reconciliation_queue(id,target_url,content,account_id,queue_item_id,attempt,next_reconcile_at,status,created_at,updated_at,reconcile_kind) VALUES(?,?,?,?,?,0,?,'pending',?,?,?)",(rid,target_url,content,account_id,queue_item_id,_iso(now+timedelta(seconds=delay_seconds)),_iso(now),_iso(now),reconcile_kind))
        return rid
    def claim_due(self,limit=5):
        now=_iso(_now()); out=[]
        with self.transaction() as conn:
            rows=conn.execute("SELECT * FROM reconciliation_queue WHERE status='pending' AND next_reconcile_at<=? ORDER BY next_reconcile_at LIMIT ?",(now,int(limit))).fetchall()
            for row in rows:
                cur=conn.execute("UPDATE reconciliation_queue SET status='running',updated_at=? WHERE id=? AND status='pending'",(now,row["id"]))
                if cur.rowcount: out.append(dict(row))
        return out
    def finish_attempt(self,rid,state,result_url='',error=''):
        now=_now()
        with self.transaction() as conn:
            row=conn.execute("SELECT attempt,reconcile_kind FROM reconciliation_queue WHERE id=?",(rid,)).fetchone()
            if not row: return None
            attempt=int(row["attempt"] or 0)+1
            kind=str(row["reconcile_kind"] or "uncertain")
            delays=self.MODERATION_DELAYS if kind == "moderation" else self.DELAYS
            if state == 'published' or (state == 'pending' and kind != 'moderation'):
                status='resolved'; next_at=None
            elif attempt>=len(delays):
                status='manual_review'; next_at=None
            else:
                status='pending'; next_at=_iso(now+timedelta(seconds=delays[attempt]))
            conn.execute("UPDATE reconciliation_queue SET attempt=?,next_reconcile_at=?,status=?,last_error=?,result_url=?,updated_at=? WHERE id=?",(attempt,next_at,status,error or None,result_url or None,_iso(now),rid))
            return status
    def recover_running(self):
        with self.transaction() as conn:
            now = _iso(_now())
            cur=conn.execute("UPDATE reconciliation_queue SET status='pending',next_reconcile_at=?,updated_at=? WHERE status='running'",(now,now))
            return cur.rowcount
    def get_item(self, rid):
        conn=self.get_conn()
        try:
            row=conn.execute("SELECT * FROM reconciliation_queue WHERE id=?",(rid,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    def list_items(self,status=None,limit=200):
        conn=self.get_conn()
        try:
            if status: rows=conn.execute("SELECT * FROM reconciliation_queue WHERE status=? ORDER BY updated_at DESC LIMIT ?",(status,int(limit))).fetchall()
            else: rows=conn.execute("SELECT * FROM reconciliation_queue ORDER BY updated_at DESC LIMIT ?",(int(limit),)).fetchall()
            return [dict(r) for r in rows]
        finally: conn.close()
