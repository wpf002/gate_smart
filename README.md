# GateSmart

AI-powered horse racing betting intelligence platform.

## Live Demo

Frontend: <https://frontend-production-de916.up.railway.app>
API:      <https://backend-production-15e941.up.railway.app>
Health:   <https://backend-production-15e941.up.railway.app/health>

**Secretariat** — the AI handicapping engine — analyzes races, interprets form, identifies value, and explains every pick in plain English.

---

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | React 18, React Router, Zustand, React Query |
| Backend | FastAPI, Python 3.13, msgspec |
| AI Engine | Anthropic Claude (Secretariat) |
| Racing Data | The Racing API (theracingapi.com) |
| Cache | Redis |
| Orchestration | Docker Compose |

---

## Quick Start

### 1. Get API Keys

**The Racing API** (horse racing data):

- Sign up at <https://www.theracingapi.com> — 2-week free trial
- Get your username and password from the dashboard

**Anthropic API** (Secretariat AI):

- Get a key at <https://console.anthropic.com>

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

Fill in:

```text
ANTHROPIC_API_KEY=sk-ant-...
RACING_API_USERNAME=your_username
RACING_API_PASSWORD=your_password
SECRET_KEY=any_random_string
```

### 3. Start

```bash
./start.sh
```

Or manually:

```bash
docker compose up --build
```

### 4. Open

- **App**: <http://localhost:3000>
- **API docs**: <http://localhost:8000/docs>

---

## Architecture

```text
gatesmart/
├── backend/
│   ├── main.py                    # FastAPI entrypoint
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── races.py           # Race card + results endpoints
│   │   │   ├── horses.py          # Horse profile + form endpoints
│   │   │   ├── ai_advisor.py      # Secretariat AI endpoints
│   │   │   ├── betting.py         # Odds + payout calculator
│   │   │   └── education.py       # Static education content
│   │   ├── core/
│   │   │   ├── config.py          # Settings from env
│   │   │   └── cache.py           # Redis cache layer
│   │   ├── models/
│   │   │   └── racing.py          # msgspec data models
│   │   └── services/
│   │       ├── racing_api.py      # The Racing API client
│   │       └── secretariat.py     # Claude AI handicapping engine
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── HomePage.jsx       # Today's races by region
│       │   ├── RaceDetailPage.jsx # Race + AI analysis + runners
│       │   ├── AdvisorPage.jsx    # Secretariat chat interface
│       │   ├── BetSlipPage.jsx    # Bet builder
│       │   ├── EducationPage.jsx  # Learn: guide, bet types, glossary
│       │   └── ProfilePage.jsx    # Bankroll + user settings
│       ├── components/
│       │   ├── races/
│       │   │   ├── RaceCard.jsx   # Race card list item
│       │   │   └── HorseRow.jsx   # Horse entry with AI scores
│       │   └── common/
│       │       └── BottomNav.jsx  # Mobile navigation
│       ├── store/                 # Zustand global state
│       ├── utils/api.js           # Axios API client
│       └── styles/globals.css     # Design system
│
├── docker-compose.yml
├── .env.example
└── start.sh
```

---

## API Endpoints

### Races

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/races/today?region=gb` | Today's race cards |
| GET | `/api/races/date/{YYYY-MM-DD}` | Race cards by date |
| GET | `/api/races/{race_id}` | Full race detail with runners |
| GET | `/api/races/results/today` | Today's results |

### Horses

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/horses/{horse_id}` | Horse profile |
| GET | `/api/horses/{horse_id}/results` | Past performances |
| GET | `/api/horses/{horse_id}/explain` | AI plain English explanation |
| GET | `/api/horses/{horse_id}/form/decode?form=1-2-3` | Decode form string |

### Secretariat (AI)

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/advisor/analyze` | Full race AI analysis |
| POST | `/api/advisor/recommend-bet` | Personalised bet recommendation |
| POST | `/api/advisor/ask` | Free-form Q&A |

### Betting

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/betting/odds/convert` | Convert odds formats |
| GET | `/api/betting/types` | All bet types with explanations |
| POST | `/api/betting/payout/calculate` | Estimate payout |

### Education

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/education/glossary` | Racing glossary |
| GET | `/api/education/beginner-guide` | Step-by-step beginner guide |
| GET | `/api/education/bankroll-guide` | Bankroll management guide |

---

## Regions

The Racing API supports: `gb`, `ire`, `usa`, `aus`, `fra`

Full UK & Ireland coverage on all plans. USA/Australia require appropriate subscription tier.

---

## Notes

- Racing API rate limit: 5 req/sec. Redis caching is built in to stay well within limits.
- Secretariat uses `claude-opus-4-20250514` for analysis — best model for nuanced handicapping.
- The app is mobile-first (max-width: 430px) but works on desktop too.
- This is an analysis/education tool. Actual bet placement requires a licensed sportsbook.
