# Helm AI fixture tour

Generated from `app.fixture_tour.run_fixture_tour()`.

## P1
Cohort: `general_needs`.

- plan_a: AED 4200; `supported`.
- plan_b: AED 8900; `supported`.
- plan_c: AED 16500; `supported`.

## P2
Cohort: `near_term_maternity`.

- plan_c: AED 16500; `supported`.
- plan_a: AED 4200; `does_not_meet_requirement`.
- plan_b: AED 8900; `does_not_meet_requirement`.

## P3
Cohort: `ongoing_chronic_care`.

- plan_b: AED 8900; `supported`.
- plan_c: AED 16500; `supported`.
- plan_a: AED 4200; `does_not_meet_requirement`.

## P4
Cohort: `general_needs`.

- plan_b: AED 8900; `supported`.
- plan_c: AED 16500; `supported`.
- plan_a: AED 4200; `does_not_meet_requirement`.

## P5
Cohort: `complex_ongoing_care`.

- plan_c: AED 16500; `supported`.
- plan_a: AED 4200; `does_not_meet_requirement`.
- plan_b: AED 8900; `does_not_meet_requirement`.

## Events

| Event | Outcome | Plan pays | Member pays | Reason |
|---|---|---:|---:|---|
| CLM-1 | covered | 1190 | 2010 | covered |
| CLM-6 | covered | 1260 | 540 | covered |
| PRE-1 | approved_with_limit | 25000 | 15000 | covered |
| CLM-2 | covered | 25000 | 15000 | covered |
| CLM-7 | denied | 0 | 3000 | sublimit_exhausted |
| CLM-3 | denied | 0 | 2800 | waiting_period_not_elapsed |
| APP-1 | upheld | 0 | 2800 | waiting_period_not_elapsed |
| CLM-8 | covered | 1680 | 920 | covered |
| CLM-4 | denied | 0 | 6000 | provider_out_of_network |
| APP-2 | overturned | 4400 | 1600 | covered |
| PRE-2 | approved | 22400 | 5600 | covered |
| CLM-5 | covered | 162000 | 18000 | covered |
| CLM-9 | insufficient_data | None | None | insufficient_data |
