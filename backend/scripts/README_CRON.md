# GateSmart Nightly Cron Schedule

## Schedule (all times ET)

| Time     | Script                    | Purpose                                                    |
|----------|---------------------------|------------------------------------------------------------|
| 08:00 AM | `nightly_predict_all.py`  | Lightweight haiku predictions for all US races             |
| 11:00 PM | `nightly_accuracy.py`     | Fetch results, settle predictions, send email digest       |
| 11:30 PM | `nightly_recalibration.py`| Update 30-day rolling calibration, inject into prompts     |

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

| Cron (UTC)      | ET time     | Script                    |
|-----------------|-------------|---------------------------|
| `0 12 * * *`    | 8:00 AM ET  | `nightly_predict_all.py`  |
| `0 3 * * *`     | 11:00 PM ET | `nightly_accuracy.py`     |
| `30 3 * * *`    | 11:30 PM ET | `nightly_recalibration.py`|

**Command for each Railway cron service:**
```
cd /app && python scripts/<script_name>.py
```

## Email Configuration (Railway env vars)

| Variable             | Value                      |
|----------------------|----------------------------|
| `GMAIL_USER`         | Your Gmail address         |
| `GMAIL_APP_PASSWORD` | 16-char Gmail App Password |
| `DAILY_REPORT_EMAIL` | wfoti71992@gmail.com       |

Generate a Gmail App Password at: https://myaccount.google.com/apppasswords
(Requires 2FA enabled on the Gmail account.)

## Cost Estimate

- `nightly_predict_all.py`: ~$0.15/day (149 races × claude-haiku at ~$0.001/race)
- `nightly_accuracy.py` email generation: ~$0.02/day (1 claude-sonnet call)
- Total: ~$0.17/day, ~$5/month
