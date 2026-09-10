# FB Automation v6.1.1 Launch Gate Handoff

Date: 2026-09-10
Branch: `v6.1.0-stability`

## Verified in this snapshot
- Production runtime regression: 172/172 PASS.
- Python production compile: 45 modules PASS.
- `node --check static/app.js`: PASS.
- Durable reconciliation queue implemented in SQLite with restart recovery and no-repost semantics.
- Runtime mutable state moved toward canonical `DATA_DIR` paths, including comment state.
- Evidence-based accounting/refactors for thread, scrape, interact, comment, job lifecycle and queue sync are included.
- M21 auth live PASS and existing-group Join live PASS were verified before this commit.
- M21 launch RC post at 2026-09-10 19:28 was confirmed published in SQLite.
- Published permalink: `https://www.facebook.com/groups/1584425176752100/permalink/1584588406735777/`.

## Not yet launch-complete
- Exact-post Facebook 2026 DOM resolver still needs live repair for scrape/comment.
- Live scrape on the permalink loaded the correct post URL/title but failed to lock DOM to the exact post scope.
- Therefore COMMENT_VERIFIED is intentionally not claimed.
- Durable-first reconcile code is present, but should be re-run live from this committed snapshot.
- Production deploy/E2E, release ZIP and SHA256 remain for the next section.

## Next section start order
1. Re-run durable reconcile for the known M21 permalink without reposting.
2. Probe exact permalink DOM once; repair shared exact-post resolver fail-closed.
3. Verify scrape exact post.
4. Post one disposable verification comment and require `COMMENT_VERIFIED` evidence.
5. Run final full regression/compile/JS check.
6. Deploy production runtime and execute production E2E.
7. Build final portable ZIP and record SHA256.

Do not create another Facebook post for the 19:28 marker; use the persisted permalink above.
