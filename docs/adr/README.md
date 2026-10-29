# Architecture decision records

The 27 decisions accepted for motui 2.0 through 2.1.2, in numeric order.
Each record has the same five sections: Context, Decision, Why, Consequences
and Alternatives. A record is history: it explains why the tree looks the
way it does, including decisions that remove a 1.x name. The current API is
what [CONTRACT](../CONTRACT.md) and [WIDGETS](../WIDGETS.md) describe.

| ADR | Title | Status |
|---|---|---|
| [001](ADR-001.md) | Surface is the only frame type | Accepted |
| [002](ADR-002.md) | No measure/render split | Accepted |
| [003](ADR-003.md) | Capabilities are attributes, interaction is hooks | Accepted |
| [004](ADR-004.md) | Delete Revisioned | Accepted |
| [005](ADR-005.md) | kernel has no I/O | Accepted |
| [006](ADR-006.md) | Timers schedule by deadline | Accepted |
| [007](ADR-007.md) | Dispatch order is data | Accepted |
| [008](ADR-008.md) | Golden frames are semantic | Accepted |
| [009](ADR-009.md) | 2.0 is intentionally incompatible | Accepted |
| [010](ADR-010.md) | The performance ceiling is 30 fps | Accepted |
| [011](ADR-011.md) | Grow without placeholder fields | Accepted |
| [012](ADR-012.md) | Wrapping is a content policy | Accepted |
| [013](ADR-013.md) | Scroll is a 2D value; horizontal windows ship in 2.0 | Accepted |
| [014](ADR-014.md) | Screen is an ABC | Accepted |
| [015](ADR-015.md) | Terminal metrics stay out of Constraints | Accepted |
| [016](ADR-016.md) | Values own behavior | Accepted |
| [017](ADR-017.md) | One concept, one door | Accepted |
| [018](ADR-018.md) | TerminalOptions and MouseMode | Accepted |
| [019](ADR-019.md) | add/get/remove return a Section; position is an enum | Accepted |
| [020](ADR-020.md) | A command declaration wires itself | Accepted |
| [021](ADR-021.md) | Focus is derived from the tree | Accepted |
| [022](ADR-022.md) | One-shot results are take() | Accepted |
| [023](ADR-023.md) | Results are pulled, not pushed | Accepted |
| [024](ADR-024.md) | Pixel is a medium, not kernel core | Accepted |
| [025](ADR-025.md) | Scene entry is the one reset door | Accepted |
| [026](ADR-026.md) | Tests pin contracts, not implementation | Accepted |
| [027](ADR-027.md) | Composition is transparent overlay | Accepted (2.1.2) |
| [028](ADR-028.md) | Drawing sizes explicitly and renders purely | Accepted (2.1.2) |
| [029](ADR-029.md) | State, verbs and results are one vocabulary | Accepted (2.1.2) |
| [030](ADR-030.md) | Control styling is shared roles plus overlays | Accepted (2.1.2) |
