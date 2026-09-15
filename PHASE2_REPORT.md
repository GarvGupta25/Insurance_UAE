# Phase 2 report

The API already rejected direct submission while a recommendation was pending and enforced assignment checks on broker-specific review endpoints. This phase additionally prevents a broker from approving a recommendation after its source profile changes: the recommendation is marked `stale` and approval returns HTTP 409. The existing test suite covers pending submission and cross-tenant broker access; full verification was rerun after the stale guard.
