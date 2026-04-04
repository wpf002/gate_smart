/**
 * API client tests — axios calls are mocked so no real network required.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

vi.mock('axios', () => {
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
  };
  return {
    default: {
      create: vi.fn(() => instance),
    },
    __instance: instance,
  };
});

// Import AFTER mocking so the module picks up the fake instance
const apiModule = await import('../utils/api.js');
const {
  getRacesToday,
  getRacesByDate,
  getRaceDetail,
  getResultsToday,
  getHorse,
  explainHorse,
  searchHorses,
  analyzeRace,
  recommendBet,
  askAdvisor,
  getGlossary,
  getBeginnerGuide,
  getBankrollGuide,
  convertOdds,
  calculatePayout,
} = apiModule;

// Grab the mocked axios instance created inside api.js
const mockAxios = axios.create();

beforeEach(() => {
  vi.clearAllMocks();
});

function mockGet(data) {
  mockAxios.get.mockResolvedValueOnce({ data });
}
function mockPost(data) {
  mockAxios.post.mockResolvedValueOnce({ data });
}

// ── Races ─────────────────────────────────────────────────────────────────────

describe('getRacesToday', () => {
  it('calls GET /races/today and returns data', async () => {
    mockGet({ racecards: [] });
    const result = await getRacesToday();
    expect(mockAxios.get).toHaveBeenCalledWith('/races/today');
    expect(result).toEqual({ racecards: [] });
  });
});

describe('getRacesByDate', () => {
  it('calls GET /races/date/:date', async () => {
    mockGet({ racecards: [] });
    await getRacesByDate('2025-06-01');
    expect(mockAxios.get).toHaveBeenCalledWith('/races/date/2025-06-01');
  });
});

describe('getRaceDetail', () => {
  it('calls GET /races/:id and returns race data', async () => {
    const race = { race_id: 'abc', course: 'Ascot', runners: [] };
    mockGet(race);
    const result = await getRaceDetail('abc');
    expect(mockAxios.get).toHaveBeenCalledWith('/races/abc');
    expect(result).toEqual(race);
  });
});

describe('getResultsToday', () => {
  it('calls GET /races/results/today', async () => {
    mockGet([]);
    await getResultsToday();
    expect(mockAxios.get).toHaveBeenCalledWith('/races/results/today');
  });
});

// ── Horses ────────────────────────────────────────────────────────────────────

describe('getHorse', () => {
  it('calls GET /horses/:id', async () => {
    mockGet({ horse_id: 'h1', horse_name: 'Test' });
    const result = await getHorse('h1');
    expect(mockAxios.get).toHaveBeenCalledWith('/horses/h1');
    expect(result.horse_name).toBe('Test');
  });
});

describe('explainHorse', () => {
  it('calls GET /horses/:id/explain', async () => {
    mockGet({ verdict: 'Strong contender' });
    await explainHorse('h1');
    expect(mockAxios.get).toHaveBeenCalledWith('/horses/h1/explain');
  });
});

describe('searchHorses', () => {
  it('calls GET /horses/search with q param', async () => {
    mockGet({ horses: [] });
    await searchHorses('Frankel');
    expect(mockAxios.get).toHaveBeenCalledWith('/horses/search', {
      params: { q: 'Frankel' },
    });
  });
});

// ── AI Advisor ────────────────────────────────────────────────────────────────

describe('analyzeRace', () => {
  it('calls POST /advisor/analyze with correct body', async () => {
    mockPost({ confidence: 'high' });
    await analyzeRace('r1', 'aggressive', 1000);
    expect(mockAxios.post).toHaveBeenCalledWith('/advisor/analyze', {
      race_id: 'r1',
      mode: 'aggressive',
      bankroll: 1000,
    });
  });

  it('defaults mode to balanced and bankroll to null', async () => {
    mockPost({});
    await analyzeRace('r1');
    expect(mockAxios.post).toHaveBeenCalledWith('/advisor/analyze', {
      race_id: 'r1',
      mode: 'balanced',
      bankroll: null,
    });
  });
});

describe('recommendBet', () => {
  it('calls POST /advisor/recommend with snake_case keys', async () => {
    mockPost({});
    await recommendBet('r1', 200, 'low', 'beginner');
    expect(mockAxios.post).toHaveBeenCalledWith('/advisor/recommend', {
      race_id: 'r1',
      bankroll: 200,
      risk_tolerance: 'low',
      experience_level: 'beginner',
    });
  });
});

describe('askAdvisor', () => {
  it('calls POST /advisor/ask with question and null context by default', async () => {
    mockPost({ answer: 'Each-way means…' });
    await askAdvisor('What is each way?');
    expect(mockAxios.post).toHaveBeenCalledWith('/advisor/ask', {
      question: 'What is each way?',
      context: null,
    });
  });

  it('passes context when provided', async () => {
    mockPost({ answer: '...' });
    await askAdvisor('Who should I back?', { race_id: 'r1' });
    expect(mockAxios.post).toHaveBeenCalledWith('/advisor/ask', {
      question: 'Who should I back?',
      context: { race_id: 'r1' },
    });
  });
});

// ── Education ─────────────────────────────────────────────────────────────────

describe('getGlossary', () => {
  it('calls GET /education/glossary', async () => {
    mockGet({ terms: [] });
    await getGlossary();
    expect(mockAxios.get).toHaveBeenCalledWith('/education/glossary');
  });
});

describe('getBeginnerGuide', () => {
  it('calls GET /education/beginner-guide', async () => {
    mockGet({ title: 'Guide', steps: [] });
    await getBeginnerGuide();
    expect(mockAxios.get).toHaveBeenCalledWith('/education/beginner-guide');
  });
});

describe('getBankrollGuide', () => {
  it('calls GET /education/bankroll-guide', async () => {
    mockGet({ strategies: [] });
    await getBankrollGuide();
    expect(mockAxios.get).toHaveBeenCalledWith('/education/bankroll-guide');
  });
});

// ── Betting utilities ─────────────────────────────────────────────────────────

describe('convertOdds', () => {
  it('calls GET /betting/convert with correct params', async () => {
    mockGet({ decimal: 3.5 });
    await convertOdds('5/2', 'decimal');
    expect(mockAxios.get).toHaveBeenCalledWith('/betting/convert', {
      params: { odds: '5/2', to_format: 'decimal' },
    });
  });
});

describe('calculatePayout', () => {
  it('calls GET /betting/payout with defaults', async () => {
    mockGet({ total_return: 35, profit: 25 });
    await calculatePayout(10, '5/2');
    expect(mockAxios.get).toHaveBeenCalledWith('/betting/payout', {
      params: { stake: 10, odds: '5/2', bet_type: 'win', each_way: false },
    });
  });

  it('passes each_way flag when true', async () => {
    mockGet({ total_return: 22, profit: 12 });
    await calculatePayout(10, '5/2', 'win', true);
    expect(mockAxios.get).toHaveBeenCalledWith('/betting/payout', {
      params: { stake: 10, odds: '5/2', bet_type: 'win', each_way: true },
    });
  });
});
