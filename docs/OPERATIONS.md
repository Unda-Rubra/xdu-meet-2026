# Event operation card

## Before admitting players

1. Confirm the deployed world/adapter receipt matches the intended release and the active backend health checks pass. Run `./scripts/racectl status`; use `./scripts/racectl --groups 3 status` to inspect all three provisioned worlds.
2. Confirm event-network firewall, offline-identity policy, empty OP/proxy administrator lists, organizer attendance roster and cached required resource pack.
3. Validate round-N roster: no duplicate or case-ambiguous names; group membership and offline UUIDs agree. Keep the same players throughout all six tracks.
4. Review the six real tracks in the selected preset. AI and automatic fill remain disabled. Do not use native Save State or global settings menus to configure an active event.

## Start one Grand Prix

```sh
./scripts/racectl preset gp1 --round 1
./scripts/route-roster --round 1
./scripts/racectl start
./scripts/racectl status
```

Preset activation and start are acknowledged by each backend. Prepare requires every expected player present. Start is **not a distributed atomic transaction**: if one backend fails, inspect all actual states. Repeating start for an already-started attempt does not start it again. Mixed armed/running states are refused rather than automatically rewound.

Players may use `/server` to navigate, but joining the wrong race server does not grant that group's membership. A disconnected entrant remains in the result roster; mid-race rejoin does not create another finish opportunity. Unresolved results remain for the judge.

## Natural completion, archive and regroup

Wait for **all active groups** to report `GP_FINISHED`, track6. An omitted C world is not part of this GP. Native `gpRound=7` can be the ceremony sentinel; the adapter must remain at track6 and closed to further starts. This native sentinel is unrelated to the event's seventh GP.

```sh
./scripts/racectl export --round 1 --attempt ATTEMPT_ID
./scripts/route-roster --round 1 --lobby --archive exports/EXPORT_ID
./scripts/racectl reset --archive exports/EXPORT_ID --reason 'Round 1 archived; regroup for round 2'
./scripts/racectl preset gp2 --round 2
./scripts/route-roster --round 2
./scripts/racectl start
```

Use the actual attempt and export directory printed by the CLI. Grouping is organizer-controlled between GPs; put A/B or A/B/C in the next round's roster before loading it. There is no central grouping service. Configure 1–7 GPs, each with six maps (up to 42 races per participating player); each player receives at most one external score award per GP. Archive and reset the previous groups before changing active worlds; the controller also checks newly included worlds are IDLE.

## Read-only snapshots

`racectl export` works during a race or after all players leave. It sends only storage reads and online-list queries, never save-all, function calls, ticking or “mark exported” writes. Captured start/finish facts are independent of the current online list. Exports contain:

- One server JSON snapshot per backend, with separately sampled `online_now_by_uuid`.
- `tracks.csv`: one row per roster participant per track, including unstarted/unfinished/disconnected states.
- `grand_prix.csv`: one row per participant/GP attempt, all six track states, raw observed native totals and captured award sums. Native totals and captured sums are distinct evidence, not interchangeable official scores.
- A manifest with server states, revisions, hashes, errors, warnings and completeness/coherence flags.

`complete` means all selected backends were read successfully. `coherent_attempt` means they describe the same GP attempt/preset; a recovery snapshot may be complete but incoherent. Neither flag means sporting results are adjudicated. No external event points are computed.

Every export gets a new directory. Logical result identity excludes export ID, so repeated snapshots do not represent additional scores. Multiple attempts for one round require explicit `--attempt`; do not sum replays. Archive receipts must contain hashed snapshots and CSVs, and must match the current final revision before reset.

## Safe stop

Normal stop refuses active racing:

```sh
./scripts/racectl stop --reason 'No active race; end session'
```

For a deliberate interruption:

```sh
./scripts/racectl stop --force --reason 'Document the operational reason'
```

The controller closes the start gate and establishes a native tick barrier, archives the current facts, then invokes the guarded native cancellation path. If any stage is unconfirmed, it reports failure and performs **no automatic rollback or container kill**. Interrupted results are not natural completions.

An explicitly reviewed ERROR/partial preset can be recovered with:

```sh
./scripts/racectl stop --force --acknowledge-error --reason 'State examined; retain interrupted attempt for judge review'
```

This is not a command to guess away unknown state. Check all backends and inspect exported evidence first. If a server is unreachable, restore connectivity before coordinated destructive control. Repeat export after a stopped state is confirmed, then reset with that final receipt. Partial-reset retry accepts only the exact prior receipt recorded by already-reset servers.

## Failure matrix

| Failure | Required response |
| --- | --- |
| Host lock busy | Another CLI is active. Do not bypass the lock; wait for its result. |
| Preset staging/activation failure | Read all states. Do not start. Retain the partial recovery snapshot; reviewed stop/reset before a new attempt. |
| Some servers started, others did not | Do not repeat blanket start. Record real states, force-stop/retain the attempt if necessary, then create a new attempt. |
| Export is partial or changing | No reset. Resolve unavailable backend or wait for stable captured revision; run another read-only export. |
| World restarted during race | Backend enters ERROR for uncertain continuity. Preserve evidence and obtain judge/operator decision; never silently resume or fabricate lost final ticks. |
| AI detected or settings differ | ERROR; next track must not start. Preserve evidence, identify the setting/spawn path, repair only after safe archival. |
| Client resource-pack load is slow | Pre-cache in batches from the author; do not send players onward before entry finishes. A routing command reports only confirmed backend arrival. |
| Native item-frame warnings | The release emits these in vanilla as well as Paper. Keep logs; do not suppress or label them repaired. Verify gameplay and podium presentation in rehearsal. |
| Capacity question | Use measurements on the actual M4 Mac mini. Local six-client tests are not 50-player certification. |

## Shutdown

First finish/stop and export the GP. Then use `docker compose -p xdu-event stop --timeout 60`. This is process shutdown **after** tournament archival, not the implementation of `racectl stop`. Never use `docker compose down -v` to reset an event.

## Acceptance status

Current evidence and unpassed gates belong in `docs/verification/`. Controlled finish-event injection verifies capture, settlement and transitions but is not proof of human-driven lap completion. Formal participant rehearsal and target-host capacity must be reported separately; do not claim readiness from container health alone.
