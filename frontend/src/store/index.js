import { create } from 'zustand';
import { persist } from 'zustand/middleware';

function generateSessionId() {
  const array = new Uint8Array(24);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
}

export const useAppStore = create(
  persist(
    (set) => ({
      // Session ID for paper trading (guest mode) — cryptographically random
      sessionId: localStorage.getItem('gs_session_id') || (() => {
        const id = generateSessionId();
        localStorage.setItem('gs_session_id', id);
        return id;
      })(),

      // Auth — JWT token + server user profile
      authToken: null,
      authUser: null,
      setAuth: (token, user) => set({ authToken: token, authUser: user }),
      clearAuth: () => set({ authToken: null, authUser: null }),

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
        authToken: state.authToken,
        authUser: state.authUser,
        userProfile: state.userProfile,
        betSlip: state.betSlip,
        // advisorMessages, valueAlerts intentionally not persisted
      }),
    }
  )
);
