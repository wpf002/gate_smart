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
      resetOnboarding: () => {
        localStorage.removeItem('gs_onboarded');
        set({ onboardingComplete: false });
      },

      // User profile. `timezone: 'local'` is the Auto option — race times always
      // follow the device's current IANA zone (read at render time), so a user
      // who travels sees correct times automatically without changing settings.
      userProfile: {
        bankroll: 500,
        riskTolerance: 'medium',
        experienceLevel: 'beginner',
        region: 'usa',
        timezone: 'local',
      },
      setUserProfile: (updates) =>
        set((state) => ({
          userProfile: { ...state.userProfile, ...updates },
        })),

      // Bet slip
      betSlip: [],
      betSlipToast: null,          // { message, id } — shown briefly then cleared
      addToBetSlip: (bet) =>
        set((state) => {
          const exists = state.betSlip.find(
            (b) =>
              b.horse_id === bet.horse_id &&
              b.bet_type === bet.bet_type &&
              b.race_id === bet.race_id
          );
          if (exists) {
            return {
              betSlipToast: {
                message: `${bet.horse_name} (${bet.bet_type}) is already in your slip`,
                id: Date.now(),
              },
            };
          }
          return {
            betSlip: [...state.betSlip, {
              ...bet,
              stake: bet.stake ?? 10,
              placed_at: new Date().toISOString(),
            }],
            betSlipToast: {
              message: `${bet.horse_name} added to slip`,
              id: Date.now(),
            },
          };
        }),
      clearBetSlipToast: () => set({ betSlipToast: null }),
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

      // Last visited race id — lets the Races nav tab return the user to the
      // race they were viewing when they tabbed over to Profile/Search/etc.
      lastRaceId: null,
      setLastRaceId: (raceId) => set({ lastRaceId: raceId }),

      // Race analysis cache — in-memory only, keyed by race_id
      // Lets the user navigate to a horse profile and back without losing analysis
      raceAnalysisCache: {},
      setRaceAnalysisCache: (raceId, data) =>
        set((state) => ({
          raceAnalysisCache: {
            ...state.raceAnalysisCache,
            [raceId]: { ...data, cachedAt: Date.now() },
          },
        })),
      clearRaceAnalysisCache: (raceId) =>
        set((state) => {
          const next = { ...state.raceAnalysisCache };
          delete next[raceId];
          return { raceAnalysisCache: next };
        }),
    }),
    {
      name: 'gatesmart-v2',
      partialize: (state) => ({
        sessionId: state.sessionId,
        authToken: state.authToken,
        authUser: state.authUser,
        onboardingComplete: state.onboardingComplete,
        userProfile: state.userProfile,
        betSlip: state.betSlip,
        // advisorMessages, valueAlerts intentionally not persisted
      }),
    }
  )
);
