# Secretariat pick-accuracy baseline

**Frozen: 2026-06-03.** Use this as the reference point for judging whether the
learning loop is actually improving picks. Re-measure with
`scripts/secretariat_scorecard.py`.

## Goal
- **Target: 30–35% top-pick win rate.**
- Context: the post-time **favorite wins ~33%** of thoroughbred races. So the
  target is essentially "pick winners as well as the betting market." Below ~33%
  means the model picks winners *worse than blindly backing the favorite*.

## Baseline at freeze (2026-06-03)
- Rolling win rate: **18.5%** (sample 2,277)
- Gap to target: **~ -11.5 pts**

### Weekly cohorts (races-weighted)
| Week of | Races | Win% | ITM% |
|---------|------:|-----:|-----:|
| Apr 20  | 543 | 28.5 | 57.6 |
| Apr 27  | 656 | 28.8 | 62.5 |  ← peak
| May 04  | 613 | 16.8 | 52.4 |  ← cliff (Triple Crown season begins)
| May 11  | 414 | 19.6 | 53.9 |
| May 18  | 646 | 19.7 | 49.4 |
| May 25  | 604 | 18.2 | 47.4 |

### Loop dead vs alive
| Window | Races | Win% | ITM% |
|--------|------:|-----:|-----:|
| loop DEAD (thru 05-27)  | 3,068 | 22.6 | 54.9 |
| loop ALIVE (05-28 on)   |   520 | 19.2 | 47.7 |  ← only ~4 settled days; too small to judge

## Caveats on the baseline
- Learning loop was **silently dead** through most of May; fixed ~2026-05-28.
- **June 1–2 outage** (Anthropic credits exhausted) → no predictions those days.
- The early-May cliff coincides with **Triple Crown season** (bigger, more
  competitive fields → lower top-pick hit rate). Part of the decline is likely
  schedule/field mix, not model skill.

## Known measurement gap
- `race_predictions` does **not** store the pick's odds or field size. Without
  the pick's odds we cannot measure favorite-agreement or calibration — the
  single most predictive variable in racing. Capturing odds at predict time is
  the prerequisite for diagnosing the path to 30–35%.

## How to re-measure
```
cd backend
DATABASE_URL=<railway public proxy DSN> python scripts/secretariat_scorecard.py
```
Judge the post-fix window starting ~late June (need 3–4 clean weeks of a healthy
loop). If still ~18% with the loop running clean, the lessons aren't moving the
needle.
