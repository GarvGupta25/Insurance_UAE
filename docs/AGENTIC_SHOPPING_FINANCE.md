# Guided shopping and financial planning: synthetic-data contract

This branch adds a guided path from reviewed profile facts to an indicative PDF, ranked fictional plans, and saved financial scenarios. It uses only `backend/data/hackathon_data.json` for product prices and terms. Public regulatory/product pages informed the presentation requirements; they do not supply a price, eligibility decision, provider network, or claim forecast for these fictional plans.

## Requirements found in official sources

- The [CBUAE point-of-sale requirements](https://rulebook.centralbank.ae/en/rulebook/article-7-6) call for explaining coverage scope, deductibles, restrictions, material application disclosures and the premium-payment mechanism. Consequently, the quote and explorer keep premium, deductible, copay, waiting periods, exclusions, assumptions and payment timing visible together.
- The [CBUAE Insurance Brokers Regulation, Article 7](https://rulebook.centralbank.ae/en/rulebook/article-7-premiums-claim-settlements-refunds-and-remuneration) says clients pay primary-insurance premiums directly to insurers; brokers must not collect them. Any later live payment adapter must route the member to the insurer or an insurer-authorized checkout. The current local simulator is labelled as such.
- The [CBUAE insurance conduct rules](https://rulebook.centralbank.ae/en/rulebook/article-12-conduct-business) address pre-inception explanation of premium payment means and duration. A yearly premium divided by twelve is therefore displayed only as a budgeting equivalent until actual insurer instalment terms are verified.
- [ADNIC's individual medical information](https://www.adnic.ae/web/guest/medical-insurance) illustrates why deductible, copay and network access must be considered alongside a premium. Helm's fictional terms remain separate from ADNIC's products.

## Implemented behavior

1. The intake agent asks for the next missing profile fact. Without a Groq key, it accepts one explicit answer to the current question and proposes a typed patch for member review. With Groq configured, it can propose multiple stated facts; the member still reviews them. Saved facts determine readiness. Accepting the final conversational fact generates the indicative quote automatically; manual editing retains its visible quote action.
2. The quote ranks supported fictional plans after known hard gaps. The agent cannot make a cheap plan win by overlooking an exclusion or wait that conflicts with a stated requirement.
3. The financial agent asks for monthly premium budget, a hypothetical annual eligible outpatient spend, employer/sponsor contribution, and the cost trade-off. Drag controls call the same server calculation used by chat. A member can save scenarios per quote, see the ten most recent, and restore the latest on return.
4. The illustration uses integer fils and half-up rounding. Member-funded premium is `max(0, annual premium - stated contribution)`. For the one-year eligible in-network general outpatient illustration, member care share is `min(spend, deductible) + copay × max(0, spend - deductible)`. The displayed annual planning total adds member-funded premium and illustrated care share. No other benefit, network event, annual-limit interaction, fee or claim outcome is inferred.
5. Budget filters apply only to supported plans. If none meets the stated budget, the response identifies the gap rather than presenting an unsupported plan as a fit. Switching the priority between premium, illustrated care share and combined annual cost changes the explanation and rank, never the stored fictional premium.
6. A quote becomes stale when the saved profile or catalogue changes. New scenario previews and saves then require a fresh quote. Scenario API access is owner-scoped and saved commands are idempotent.

The production path still needs verified insurer quote and instalment terms. Groq language extraction cannot be claimed as tested here without a configured key. The current scenario is a budgeting model, not personal financial advice, a real EMI offer, a claim prediction or an insurer quotation.
