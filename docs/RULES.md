# Event rules and pending adjudication

The deployment owner explicitly accepted the Minecraft EULA for local deployment and runtime verification, and chose to leave unresolved sporting decisions pending judge review.

The owner subsequently selected **private trusted event** admission for offline clients. Proxy online authentication is disabled; the deployment remains restricted to the private event network (localhost by default). Names and offline UUIDs can be impersonated. Organizer supervision is the explicitly accepted identity control, not cryptographic authentication. Export provenance must state `offline_trusted_private`.

All administration is host/console/RCON-only. Never grant OP, native admin, tournament_admin or proxy admin permissions from an offline name or UUID. Player rosters constrain participation, but do not authenticate the human. A public unauthenticated deployment is outside this approved trust policy.

- Five Grand Prix per group; six explicit Race tracks per GP; three groups; no AI participants or automatic fill.
- Fixed offline UUID membership within a GP. Each UUID must match the proxy's deterministic OfflinePlayer:name mapping, and organizers must verify the human/name assignment. Names must remain fixed throughout the event.
- Native points are raw game evidence, not external event points.
- Preserve DNS, DNF, disconnected, incomplete, conflicting and unknown observations separately. A disconnect alone is not an adjudicated DNF.
- Equal totals, missing or disputed results, partial GP attempts and restarts remain `pending_adjudication`; never invent a final rank or award external points.
- Replays have distinct attempt IDs. No attempt is silently discarded or cumulatively counted with its replay.
- Final judge policies and the allowed start-time deviation still require explicit approval before the formal event rehearsal. The user's pending-review choice permits honest raw exports, not a claim that sporting adjudication is complete.

`config/event.yaml` uses JSON syntax, a YAML subset. Copy `config/roster.example.json` to local `config/rosters/round-N.json`, and replace empty arrays with organizer-approved participants shaped `{"uuid":"offline-uuid","name":"fixed-game-name"}`. Validate names and their deterministic offline UUIDs, unique across all groups. Empty groups fail admission. Real rosters are Git-ignored; there is no in-game administrator whitelist in this deployment mode.

The world ZIP says “Do not re-publish” and prohibits selling it or using it as a commodity. Keep the original world and resource pack local; direct participants to the author's resource URL. The owner must clarify any public redistribution or commercial event authorization before that activity. Local artifact acquisition is not evidence of a redistribution license.
