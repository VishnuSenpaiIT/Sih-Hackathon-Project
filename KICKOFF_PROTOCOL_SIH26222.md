# Kickoff Protocol — Smart Traffic Monitoring & Prediction System (SIH26222)

Steps to run at the start of every build session before any agent writes code.

## Step 1 — Context Load
Every agent reads, in order:
1. Project doc / PRD — what we're building and why
2. System architecture doc (SAD), if present
3. `BUILD_ORDER_SIH26222.md` — what to build and in what sequence
4. `MULTI_AGENT_GUIDE_SIH26222.md` — its own role and boundaries

## Step 2 — State Check
Before starting, the Orchestrator checks:
- [ ] Which BUILD_ORDER phase are we in?
- [ ] Which tasks are marked DONE vs BLOCKED from the last session?
- [ ] Has the shared data schema changed since last session?
- [ ] Are there uncommitted/unintegrated changes from any agent?

## Step 3 — Task Assignment
Orchestrator assigns each active agent exactly one current task from the current BUILD_ORDER phase, respecting dependencies. No agent is given a task whose prerequisite is not DONE.

## Step 4 — Environment Sanity Check
Run once per session (DevOps Agent owns this):
```bash
python --version   # expect 3.10+
node --version     # expect 18+
docker --version   # optional but preferred
```
Confirm `.env` exists (copy from `.env.example` if missing) and required services (Postgres/InfluxDB/Redis) are reachable or stubbed for local dev.

## Step 5 — Working Agreement for This Session
State explicitly at kickoff:
- Session goal (1 sentence)
- Which BUILD_ORDER phase/steps are in scope today
- Definition of done for today's session

## Step 6 — Execute
Agents work their assigned tasks. Each agent ends its turn with a status update in the format defined in `MULTI_AGENT_GUIDE_SIH26222.md`.

## Step 7 — Session Close-Out
Before ending:
- [ ] Update BUILD_ORDER checklist (mark DONE items)
- [ ] Log any BLOCKED items with what's needed to unblock
- [ ] Note any schema/contract changes for next session's Context Load

## Trigger Phrases
- "kickoff" / "start session" → run Steps 1-5
- "status" → Orchestrator prints current phase + per-agent DONE/BLOCKED/IN-PROGRESS
- "close out" → run Step 7
