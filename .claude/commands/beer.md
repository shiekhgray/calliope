Save current session state before context clear.

1. Read `/home/gray/calliope/.todo` and update it to reflect actual current progress:
   - Check off any tasks that are complete
   - Add any new tasks discovered during this session
   - Add any blockers or notes inline under relevant tasks
   - Reorder or reprioritize if the work has revealed that's necessary

2. Read `/home/gray/calliope/CLAUDE.md` and update it with anything learned this session:
   - Architectural decisions that were made or changed
   - New conventions established in the code
   - Gotchas, non-obvious implementation details, or things future-you should know
   - Any corrections to what was planned vs what was actually built

3. Check if any other files were mentioned or created during this session that should be documented (e.g. a new config file, a new script, a new directory). If so, reflect them in CLAUDE.md.

4. Write a brief summary to the user of what was saved — what got checked off, what changed, anything important to remember at the start of the next session.
