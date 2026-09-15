# Phase 3 report

The broker workspace now has a server-sorted, assigned-member worklist and a broker-only case record endpoint/view. The worklist includes pending recommendations, appeals, and reassessments. It applies the documented stable ordering: oldest item, urgency class, amount, then ID; every row carries a rank and explanation. Case detail exposes saved profile, deterministic cohort/flag reasons, the latest quote and recommendation, review history, policy snapshot, servicing history, and a next-action indicator only to an assigned broker.

Member endpoints were left unchanged and do not expose this internal case payload.
