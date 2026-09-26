# Live system dependency graph

This document describes the current **manual token** design, not the retired seven-round roster exporter. Exact commands are in `docs/OPERATIONS.md`; deployment and backup paths are in `docs/SETUP.md`.

```mermaid
flowchart TD
    Login[Proxy: Yggdrasil-authenticated player enters the only main lobby] --> QQ[Private QQ registration]
    QQ --> Config[Console-authorized admin configures native GP]
    Config --> Start[Explicit /gpstart or host racectl start]
    Start --> Groups[Random A/B or A/B/C from present non-admins]
    Groups --> Admission[Proxy admits assigned players and spectator commentators]
    Admission --> Track[Native track and item gameplay]
    Track --> Barrier[Wait for every active group at the same track]
    Barrier -->|more tracks| Track
    Barrier -->|last track| Awards[Native award ceremonies in each race world]
    Awards --> Lobby[All players return to main lobby]
    Lobby --> Archive[Checksum-verified local archive and token]
    Archive -->|unuploaded warmup| LocalOnly[No Feishu update]
    Archive -->|manual upload --token| Binding[Persist token to selected Feishu round]
    Binding --> Readback[Write QQ-linked scores and names; read back]
    Readback --> Publish[Switch published-batch pointer and recalculate rankings]
```

The gameplay daemon makes no periodic Feishu calls. The only background work is local administrator-command handling, per-track barrier coordination, native completion collection and archiving. All cloud mutations are explicit CLI operations. Each server reports one immutable attempt/group with a QQ and nickname snapshot; administrators never enter the score roster. No published result is inferred from proxy presence, signup, or a partially finished GP.

Verification is tiered: the real native client proves the route and lifecycle exercised; local two-player tests cannot prove 51-player capacity. See `docs/verification/README.md` for evidence and limitations. The pinned Minecraft/Bungee/runtime artifacts stay unchanged; the proxy QQ gate is a narrowly scoped custom plugin, not a replacement game server.
