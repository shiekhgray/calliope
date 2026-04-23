Load context at the start of a new session before beginning work.

1. Read `/home/gray/calliope/CLAUDE.md` in full — this is the canonical architecture reference.

2. Read `/home/gray/calliope/.todo` — identify:
   - What phase we are currently in
   - The next unchecked task(s) to work on
   - Any inline notes or blockers left from the previous session

3. Based on what phase and task is next, proactively read any directly relevant source files. For example:
   - If working on the API: read key files in `api/`
   - If working on the web app: read key files in `web/`
   - If working on Android: read key files in `android/`
   - If working on infrastructure: read `docker-compose.yml`, Dockerfiles, nginx configs

4. Write a brief session briefing to the user:
   - Current phase and where we left off
   - The next task(s) to tackle
   - Anything flagged from the previous session to keep in mind
   - A suggested first action to get moving
