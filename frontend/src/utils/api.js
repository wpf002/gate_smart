import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api`
    : '/api',
  timeout: 90000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach session ID and JWT token to every request
api.interceptors.request.use((config) => {
  try {
    const stored = JSON.parse(localStorage.getItem('gatesmart-v2') || '{}');
    const sid = stored?.state?.sessionId;
    if (sid) config.headers['X-Session-ID'] = sid;
    const token = stored?.state?.authToken;
    if (token) config.headers['Authorization'] = `Bearer ${token}`;
  } catch {
    // ignore
  }
  return config;
});

// ── Races ────────────────────────────────────────────────────────────────────
export const getRacesToday = (region = null) =>
  api.get('/races/today', { params: region ? { region } : {} }).then((r) => r.data);

export const getRacesByDate = (date, region = null) =>
  api.get(`/races/date/${date}`, { params: region ? { region } : {} }).then((r) => r.data);

export const getRaceDetail = (raceId) =>
  api.get(`/races/${raceId}`).then((r) => r.data);

export const getResultsToday = () =>
  api.get('/races/results/today').then((r) => r.data);

export const getResultsByDate = (date) =>
  api.get(`/races/results/${date}`).then((r) => r.data);

// ── Horses ────────────────────────────────────────────────────────────────────
export const getHorse = (horseId) =>
  api.get(`/horses/${horseId}`).then((r) => r.data);

export const explainHorse = (horseId) =>
  api.get(`/horses/${horseId}/explain`).then((r) => r.data.analysis);

export const searchHorses = (query) =>
  api.get('/horses/search', { params: { q: query } }).then((r) => r.data);

export const getHorsePastPerformances = (horseId, horseName) =>
  api.get(`/horses/${horseId}/past-performances`, { params: horseName ? { name: horseName } : {} }).then((r) => r.data);

// ── AI Advisor ────────────────────────────────────────────────────────────────
export const analyzeRace = (raceId, mode = 'balanced', bankroll = null) =>
  api
    .post('/advisor/analyze', { race_id: raceId, mode, bankroll })
    .then((r) => r.data);

export const recommendBet = (raceId, bankroll, riskTolerance, experienceLevel) =>
  api
    .post('/advisor/recommend-bet', {
      race_id: raceId,
      bankroll,
      risk_tolerance: riskTolerance,
      experience_level: experienceLevel,
    })
    .then((r) => r.data);

export const askAdvisor = (question, context = null) =>
  api.post('/advisor/ask', { question, context }).then((r) => r.data);

export const getScoreCard = (raceId) =>
  api.post('/advisor/scorecard', { race_id: raceId }).then((r) => r.data);

// ── Education ────────────────────────────────────────────────────────────────
export const getGlossary = () =>
  api.get('/education/glossary').then((r) => r.data);

export const getBeginnerGuide = () =>
  api.get('/education/beginner-guide').then((r) => r.data);

export const getBankrollGuide = () =>
  api.get('/education/bankroll-guide').then((r) => r.data);

export const explainFormString = (formString, horseName) =>
  api
    .post('/advisor/explain-form', { form_string: formString, horse_name: horseName })
    .then((r) => r.data);

// ── Betting utilities ─────────────────────────────────────────────────────────
export const convertOdds = (fractional, stake = 10) =>
  api
    .post('/betting/odds/convert', { fractional, stake })
    .then((r) => r.data);

export const calculatePayout = (stake, odds, betType = 'win', eachWay = false) =>
  api
    .post('/betting/payout/calculate', {
      stake,
      odds: [odds],
      bet_type: betType,
      each_way: eachWay,
    })
    .then((r) => r.data);

// ── Value Alerts ─────────────────────────────────────────────────────────────
export const checkValueAlerts = (raceId, horses) =>
  api.post('/alerts/check', { race_id: raceId, horses }).then((r) => r.data);

export const getRaceFairPrices = (raceId) =>
  api.get(`/alerts/race/${raceId}`).then((r) => r.data);

// ── Secretariat Accuracy ──────────────────────────────────────────────────────
export const getSecretariatAccuracy = () =>
  api.get('/advisor/accuracy').then((r) => r.data)

export const getDailyAccuracy = (date) =>
  api.get('/accuracy/daily', { params: date ? { date } : {} }).then((r) => r.data)

export const getAccuracyHistory = () =>
  api.get('/accuracy/history').then((r) => r.data);

// ── Race Debrief ──────────────────────────────────────────────────────────────
export const getRaceDebrief = (raceId) =>
  api.post('/advisor/debrief', { race_id: raceId }).then((r) => r.data);

// ── Analysis Cache ─────────────────────────────────────────────────────────────
export const clearRaceAnalysis = (raceId) =>
  api.delete(`/advisor/analysis/${raceId}`).then((r) => r.data);

// ── Race Results ───────────────────────────────────────────────────────────────
export const getRaceResults = (raceId) =>
  api.get(`/races/results/race/${raceId}`).then((r) => r.data);

// ── Affiliate ─────────────────────────────────────────────────────────────────
export const logAffiliateClick = (affiliateId, sessionId, raceId = '') =>
  api.post('/affiliate/click', { affiliate_id: affiliateId, session_id: sessionId, race_id: raceId })
    .then((r) => r.data).catch(() => null); // fire-and-forget, never throw

// ── Paper Trading Simulator ───────────────────────────────────────────────────
export const simPlaceBet = (bet) =>
  api.post('/simulator/bet', bet).then((r) => r.data);

export const simSettle = (raceId) =>
  api.post(`/simulator/settle/${raceId}`).then((r) => r.data);

export const simGetBets = () =>
  api.get('/simulator/bets').then((r) => r.data);

export const simGetBank = () =>
  api.get('/simulator/bank').then((r) => r.data);

export const simGetStats = () =>
  api.get('/simulator/stats').then((r) => r.data);

export const simReset = () =>
  api.post('/simulator/reset').then((r) => r.data);

export const simDeleteBet = (betId) =>
  api.delete(`/simulator/bet/${betId}`).then((r) => r.data);

export const simTopup = (amount) =>
  api.post('/simulator/bank/topup', { amount }).then((r) => r.data);

// ── Push Notifications ────────────────────────────────────────────────────────
// ── Auth ──────────────────────────────────────────────────────────────────────
export const authRegister = (email, password, profile = {}) =>
  api.post('/auth/register', { email, password, ...profile }).then((r) => r.data);

export const authLogin = (email, password) =>
  api.post('/auth/login', { email, password }).then((r) => r.data);

export const authMe = () =>
  api.get('/auth/me').then((r) => r.data);

export const authUpdateProfile = (updates) =>
  api.put('/auth/profile', updates).then((r) => r.data);

export const authLogout = () =>
  api.post('/auth/logout').then((r) => r.data);

// ── Push Notifications ────────────────────────────────────────────────────────
export const subscribeToRaceAlerts = (raceId, sessionId, playerId) =>
  api.post('/alerts/subscribe', {
    race_id: raceId,
    session_id: sessionId,
    onesignal_player_id: playerId,
  }).then((r) => r.data);

export const unsubscribeFromRaceAlerts = (raceId) =>
  api.delete(`/alerts/subscribe/${raceId}`).then((r) => r.data);

export default api;
