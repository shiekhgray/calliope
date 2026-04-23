Save current session state before context clear.

1. Read `/home/gray/calliope/.todo` and update it to reflect actual current progress:
   - Check off any tasks that are complete
   - Add any new tasks discovered during this session
   - Add any blockers or notes inline under relevant tasks
   - Reorder or reprioritize if the work has revealed that's necessary

2. Update CLAUDE.md files with anything learned this session. Edit whichever files are relevant:
   - `/home/gray/calliope/CLAUDE.md` — architecture, cross-cutting gotchas, non-obvious rules
   - `/home/gray/calliope/api/CLAUDE.md` — API/scanner changes, new routers, migration table
   - `/home/gray/calliope/web/CLAUDE.md` — frontend conventions, new pages, React Query keys
   - `/home/gray/calliope/indexer/CLAUDE.md` — similarity engine changes, vector schema
   Only update sections that actually changed. Do not rewrite sections that are still accurate.

3. Write a session record to `/home/gray/calliope/project_history/YYYY-MM-DD.md`
   (use today's actual date). If a file for today already exists, append a new `## Session N` section.
   Include:
   - Features shipped or meaningfully progressed (what changed, not just that it changed)
   - Key decisions made and why (especially non-obvious tradeoffs)
   - Gotchas discovered
   - DB/infra changes applied to production (migrations run, nginx changes, etc.)
   - What's up next

4. Write a brief summary to the user of what was saved — what got checked off, what changed,
   anything important to remember at the start of the next session.
