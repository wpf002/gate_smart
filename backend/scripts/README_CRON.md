# GateSmart Nightly Cron Schedule

## Schedule (all times ET)

Source of truth: `backend/app/core/scheduler.py` (APScheduler runs in-process when the FastAPI server starts).

| Time     | Script                     | Purpose                                                |
| -------- | -------------------------- | ------------------------------------------------------ |
| 08:00 AM | `nightly_predict_all.py`   | Full pre-race analysis for all US races                |
| 06:00 AM | `nightly_accuracy.py`      | Settle yesterday's predictions, send email digest      |
| 11:30 PM | `nightly_recalibration.py` | Update 30-day rolling calibration, inject into prompts |
| 12:00 AM | `nightly_reflect.py`       | Secretariat reflection layer                           |
| every 5m | `race_alerts` (in-process) | Push notifications for upcoming races                  |
| every 5m | `smoke_check` (in-process) | Pings prod endpoints, emails on regression (prod only) |

## Manual Run

```bash
cd backend
python scripts/nightly_predict_all.py
python scripts/nightly_accuracy.py
python scripts/nightly_recalibration.py

# Dry run (no DB writes, no email)
python scripts/nightly_predict_all.py --dry-run
python scripts/nightly_accuracy.py --dry-run
python scripts/nightly_recalibration.py --dry-run

# Specific date
python scripts/nightly_accuracy.py --date 2026-04-11
python scripts/nightly_predict_all.py --date 2026-04-11
```

## Railway Cron Setup

Railway dashboard → New Service → Cron → point to backend repo.

Schedules use UTC (Railway is UTC). ET is UTC-4 in summer, UTC-5 in winter.

| Cron (UTC)   | ET time     | Script                     |
| ------------ | ----------- | -------------------------- |
| `0 12 * * *` | 8:00 AM ET  | `nightly_predict_all.py`   |
| `0 3 * * *`  | 11:00 PM ET | `nightly_accuracy.py`      |
| `30 3 * * *` | 11:30 PM ET | `nightly_recalibration.py` |

**Command for each Railway cron service:**

```text
cd /app && python scripts/<script_name>.py
```

## Email Configuration (Railway env vars)

| Variable             | Value                                                      |
| -------------------- | ---------------------------------------------------------- |
| `GMAIL_USER`         | Your Gmail address                                         |
| `GMAIL_APP_PASSWORD` | 16-char Gmail App Password                                 |
| `DAILY_REPORT_EMAIL` | `wfoti71992@gmail.com,kenfoti@gmail.com` (comma-separated) |

Generate a Gmail App Password at: <https://myaccount.google.com/apppasswords>
(Requires 2FA enabled on the Gmail account.)

## Cost Estimate

> **STALE — do not trust the figures below.** They were written for a Haiku-only,
> pre-batch, pre-A/B world and understate real spend by roughly 20x. A 50% Sonnet 4.6
> A/B (`PICK_MODEL_AB_PERCENT`) and full-analysis writes landed later. Measured burn is
> ~$75-190/month. Get the real number from `GET /api/admin/cost/summary`, which reads
> the `llm_call_log` table.

- `nightly_predict_all.py`: ~$0.15/day (149 races × claude-haiku at ~$0.001/race)
- `nightly_accuracy.py` email generation: ~$0.02/day (1 claude-sonnet call)
- Total: ~$0.17/day, ~$5/month
