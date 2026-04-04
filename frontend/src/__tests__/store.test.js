/**
 * Store tests — Zustand state logic (no DOM needed).
 * Each test uses a fresh store instance via act() resets.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '../store';

// Reset store to initial state before each test
beforeEach(() => {
  useAppStore.setState({
    userProfile: {
      bankroll: 500,
      riskTolerance: 'medium',
      experienceLevel: 'beginner',
      name: '',
    },
    betSlip: [],
    advisorMessages: [],
  });
});

// ── userProfile ───────────────────────────────────────────────────────────────

describe('userProfile', () => {
  it('has correct initial state', () => {
    const { userProfile } = useAppStore.getState();
    expect(userProfile.bankroll).toBe(500);
    expect(userProfile.riskTolerance).toBe('medium');
    expect(userProfile.experienceLevel).toBe('beginner');
    expect(userProfile.name).toBe('');
  });

  it('setUserProfile merges partial updates', () => {
    useAppStore.getState().setUserProfile({ bankroll: 1000, name: 'Will' });
    const { userProfile } = useAppStore.getState();
    expect(userProfile.bankroll).toBe(1000);
    expect(userProfile.name).toBe('Will');
    // Untouched fields preserved
    expect(userProfile.riskTolerance).toBe('medium');
    expect(userProfile.experienceLevel).toBe('beginner');
  });

  it('setUserProfile can update risk tolerance', () => {
    useAppStore.getState().setUserProfile({ riskTolerance: 'high' });
    expect(useAppStore.getState().userProfile.riskTolerance).toBe('high');
  });

  it('setUserProfile can update experience level', () => {
    useAppStore.getState().setUserProfile({ experienceLevel: 'advanced' });
    expect(useAppStore.getState().userProfile.experienceLevel).toBe('advanced');
  });
});

// ── betSlip ───────────────────────────────────────────────────────────────────

const makeBet = (overrides = {}) => ({
  horse_id: 'h1',
  horse_name: 'Secretariat',
  race_id: 'r1',
  bet_type: 'win',
  odds: '5/2',
  stake: 10,
  ...overrides,
});

describe('betSlip — addToBetSlip', () => {
  it('adds a bet to an empty slip', () => {
    useAppStore.getState().addToBetSlip(makeBet());
    const { betSlip } = useAppStore.getState();
    expect(betSlip).toHaveLength(1);
    expect(betSlip[0].horse_name).toBe('Secretariat');
  });

  it('defaults stake to 10 when not provided', () => {
    useAppStore.getState().addToBetSlip(makeBet({ stake: undefined }));
    expect(useAppStore.getState().betSlip[0].stake).toBe(10);
  });

  it('uses provided stake when given', () => {
    useAppStore.getState().addToBetSlip(makeBet({ stake: 25 }));
    expect(useAppStore.getState().betSlip[0].stake).toBe(25);
  });

  it('does not add duplicate (same horse_id + bet_type)', () => {
    useAppStore.getState().addToBetSlip(makeBet());
    useAppStore.getState().addToBetSlip(makeBet());
    expect(useAppStore.getState().betSlip).toHaveLength(1);
  });

  it('allows same horse with different bet_type', () => {
    useAppStore.getState().addToBetSlip(makeBet({ bet_type: 'win' }));
    useAppStore.getState().addToBetSlip(makeBet({ bet_type: 'place' }));
    expect(useAppStore.getState().betSlip).toHaveLength(2);
  });

  it('allows different horses with same bet_type', () => {
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h1' }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h2' }));
    expect(useAppStore.getState().betSlip).toHaveLength(2);
  });

  it('can add multiple different bets', () => {
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h1', bet_type: 'win' }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h2', bet_type: 'win' }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h3', bet_type: 'each_way' }));
    expect(useAppStore.getState().betSlip).toHaveLength(3);
  });
});

describe('betSlip — removeFromBetSlip', () => {
  it('removes the matching bet', () => {
    useAppStore.getState().addToBetSlip(makeBet());
    useAppStore.getState().removeFromBetSlip('h1', 'win');
    expect(useAppStore.getState().betSlip).toHaveLength(0);
  });

  it('only removes the exact horse_id + bet_type combination', () => {
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h1', bet_type: 'win' }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h1', bet_type: 'place' }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h2', bet_type: 'win' }));
    useAppStore.getState().removeFromBetSlip('h1', 'win');
    const slip = useAppStore.getState().betSlip;
    expect(slip).toHaveLength(2);
    expect(slip.find((b) => b.horse_id === 'h1' && b.bet_type === 'win')).toBeUndefined();
  });

  it('does nothing when bet does not exist', () => {
    useAppStore.getState().addToBetSlip(makeBet());
    useAppStore.getState().removeFromBetSlip('h99', 'win');
    expect(useAppStore.getState().betSlip).toHaveLength(1);
  });
});

describe('betSlip — updateStake', () => {
  it('updates stake for matching bet', () => {
    useAppStore.getState().addToBetSlip(makeBet({ stake: 10 }));
    useAppStore.getState().updateStake('h1', 'win', 50);
    expect(useAppStore.getState().betSlip[0].stake).toBe(50);
  });

  it('only updates the targeted bet', () => {
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h1', bet_type: 'win', stake: 10 }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h2', bet_type: 'win', stake: 10 }));
    useAppStore.getState().updateStake('h1', 'win', 30);
    const slip = useAppStore.getState().betSlip;
    expect(slip.find((b) => b.horse_id === 'h1').stake).toBe(30);
    expect(slip.find((b) => b.horse_id === 'h2').stake).toBe(10);
  });
});

describe('betSlip — clearBetSlip', () => {
  it('empties the slip', () => {
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h1' }));
    useAppStore.getState().addToBetSlip(makeBet({ horse_id: 'h2' }));
    useAppStore.getState().clearBetSlip();
    expect(useAppStore.getState().betSlip).toHaveLength(0);
  });

  it('is safe to call on an empty slip', () => {
    expect(() => useAppStore.getState().clearBetSlip()).not.toThrow();
    expect(useAppStore.getState().betSlip).toHaveLength(0);
  });
});

// ── advisorMessages ───────────────────────────────────────────────────────────

describe('advisorMessages', () => {
  it('starts empty', () => {
    expect(useAppStore.getState().advisorMessages).toHaveLength(0);
  });

  it('addAdvisorMessage appends a message', () => {
    useAppStore.getState().addAdvisorMessage({ role: 'user', content: 'Hello' });
    const msgs = useAppStore.getState().advisorMessages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0]).toEqual({ role: 'user', content: 'Hello' });
  });

  it('preserves message order', () => {
    useAppStore.getState().addAdvisorMessage({ role: 'user', content: 'Q1' });
    useAppStore.getState().addAdvisorMessage({ role: 'assistant', content: 'A1' });
    useAppStore.getState().addAdvisorMessage({ role: 'user', content: 'Q2' });
    const msgs = useAppStore.getState().advisorMessages;
    expect(msgs[0].content).toBe('Q1');
    expect(msgs[1].content).toBe('A1');
    expect(msgs[2].content).toBe('Q2');
  });

  it('clearAdvisorMessages empties the list', () => {
    useAppStore.getState().addAdvisorMessage({ role: 'user', content: 'test' });
    useAppStore.getState().clearAdvisorMessages();
    expect(useAppStore.getState().advisorMessages).toHaveLength(0);
  });
});
