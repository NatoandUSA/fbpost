# FB Automation v6.1.1 Comment Gate Handoff

Date: 2026-09-10
Branch: `v6.1.0-stability`
Base commit: `496eb0191b753ed50d464bed6699d683dff0be41`

## Verified in this section
- Durable reconcile on existing M21 post returned `RECONCILE_PUBLISHED` from SQLite evidence; no repost occurred.
- Launch RC permalink remains `https://www.facebook.com/groups/1584425176752100/permalink/1584588406735777/`.
- Shared exact-post resolver now fails closed: exact identity article first; otherwise exactly one visible permalink dialog while URL contains the expected post ID.
- Unsafe single-visible-article fallback was removed.
- Live M21 scrape passed `SCRAPE_VERIFIED` on post ID `1584588406735777` after resolver patch.
- Comment success contract now requires persistence after reopening the exact permalink before returning literal `COMMENT_VERIFIED`.
- Facebook 2026 transparent-overlay pointer interception no longer requires a normal textbox click; DOM focus/human_type fallback is used.
- Final regression after the last patch: 172/172 PASS.
- Production Python compile: 45 modules PASS.
- `node --check static/app.js`: PASS.

## Launch blocker retained intentionally
- The first live comment appeared immediately after submit, but a read-only reopen probe found no persisted marker. That result is explicitly not accepted as `COMMENT_VERIFIED`.
- After hardening verification, a new live attempt failed before submit with `COMMENT_INPUT_NOT_FOUND`: exact post scope was found, but Facebook did not mount a usable comment textbox on that reopen.
- Another attempt hit Facebook's transparent overlay intercepting pointer events; the focus path was hardened afterward.
- Therefore this snapshot is an RC/stability checkpoint, not a final production-launch declaration.

## Next section start order
1. Start from this checkpoint commit; do not create another launch post.
2. Use the same persisted M21 permalink only.
3. Probe the Facebook 2026 comment surface read-only to distinguish collapsed comment UI, overlay, lazy-mounted editor, and permission/state variants.
4. Repair comment-input resolver without weakening exact-post scope.
5. Run one controlled disposable comment and require literal `COMMENT_VERIFIED` plus persistence after reopen.
6. Re-run scrape and confirm the persisted verification comment can be observed/extracted or document why the comment extractor legitimately returns zero.
7. Run 172-test regression, 45-module compile and JS syntax check again.
8. Only then promote RC to final production deploy/E2E and final release artifact.

Do not repost marker `FB-AUTO LAUNCH RC 2026-09-10 19:28`.
