# Broker worklist ordering

Work is ordered deterministically: oldest unresolved item first; then insufficient-data servicing items and appeals before recommendations and reassessments; then larger billed, estimated, or annual-premium amount; and finally stable item ID. Each queue entry includes its rank and a plain-language reason.
