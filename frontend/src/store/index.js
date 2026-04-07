import { create } from 'zustand';
import { persist } from 'zustand/middleware';

function generateSessionId() {
  return 'gs_' + Math.random().toString(36).slice(2, 11) + Date.now().toString(36);
}

export const useAppStore = create(
  persist(
    (set) => ({
      // Session ID for paper trading (generated once, persisted)
      sessionId: generateSessionId(),

      // Onboarding
      onboardingComplete: localStorage.getItem('gs_onboarded') === 'true',
      completeOnboarding: () => {
        localStorage.setItem('gs_onboarded', 'true');
        set({ onboardingComplete: true });
      },

      // User profile
      userProfile: {
        bankroll: 500,
        riskTolerance: 'medium',
        experienceLevel: 'beginner',
        region: 'usa',
        name: '',
      },
      setUserProfile: (updates) =>
        set((state) => ({
          userProfile: { ...state.userProfile, ...updates },
        })),

      // Bet slip
      betSlip: [],
      addToBetSlip: (bet) =>
        set((state) => {
          const exists = state.betSlip.find(
            (b) => b.horse_id === bet.horse_id && b.bet_type === bet.bet_type
          );
          if (exists) return state;
          return { betSlip: [...state.betSlip, { ...bet, stake: bet.stake ?? 10 }] };
        }),
      removeFromBetSlip: (horse_id, bet_type) =>
        set((state) => ({
          betSlip: state.betSlip.filter(
            (b) => !(b.horse_id === horse_id && b.bet_type === bet_type)
          ),
        })),
      updateStake: (horse_id, bet_type, stake) =>
        set((state) => ({
          betSlip: state.betSlip.map((b) =>
            b.horse_id === horse_id && b.bet_type === bet_type
              ? { ...b, stake }
              : b
          ),
        })),
      clearBetSlip: () => set({ betSlip: [] }),

      // Advisor messages
      advisorMessages: [],
      addAdvisorMessage: (message) =>
        set((state) => ({
          advisorMessages: [...state.advisorMessages, message],
        })),
      clearAdvisorMessages: () => set({ advisorMessages: [] }),

      // Value alerts keyed by race_id
      valueAlerts: {},
      setValueAlerts: (raceId, alerts) =>
        set((state) => ({
          valueAlerts: { ...state.valueAlerts, [raceId]: alerts },
        })),
    }),
    {
      name: 'gatesmart-v2',
      partialize: (state) => ({
        sessionId: state.sessionId,
        userProfile: state.userProfile,
        betSlip: state.betSlip,
        // advisorMessages, valueAlerts intentionally not persisted
      }),
    }
  )
);
