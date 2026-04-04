import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Races ────────────────────────────────────────────────────────────────────
export const getRacesToday = () =>
  api.get('/races/today').then((r) => r.data);

export const getRacesByDate = (date) =>
  api.get(`/races/date/${date}`).then((r) => r.data);

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
  api.get(`/horses/${horseId}/explain`).then((r) => r.data);

export const searchHorses = (query) =>
  api.get('/horses/search', { params: { q: query } }).then((r) => r.data);

// ── AI Advisor ────────────────────────────────────────────────────────────────
export const analyzeRace = (raceId, mode = 'balanced', bankroll = null) =>
  api
    .post('/advisor/analyze', { race_id: raceId, mode, bankroll })
    .then((r) => r.data);

export const recommendBet = (raceId, bankroll, riskTolerance, experienceLevel) =>
  api
    .post('/advisor/recommend', {
      race_id: raceId,
      bankroll,
      risk_tolerance: riskTolerance,
      experience_level: experienceLevel,
    })
    .then((r) => r.data);

export const askAdvisor = (question, context = null) =>
  api.post('/advisor/ask', { question, context }).then((r) => r.data);

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
export const convertOdds = (odds, toFormat) =>
  api
    .get('/betting/convert', { params: { odds, to_format: toFormat } })
    .then((r) => r.data);

export const calculatePayout = (stake, odds, betType = 'win', eachWay = false) =>
  api
    .get('/betting/payout', {
      params: { stake, odds, bet_type: betType, each_way: eachWay },
    })
    .then((r) => r.data);

export default api;
