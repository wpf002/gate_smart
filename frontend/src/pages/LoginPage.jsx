import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import PageHeader from '../components/common/PageHeader';
import { authLogin, authRegister } from '../utils/api';
import { useAppStore } from '../store';

export default function LoginPage() {
  const [tab, setTab] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');

  const { setAuth, userProfile } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();
  // Always send to home after sign-in — Profile sends state.from='/profile' on logout
  // but returning there is confusing; home is the natural landing page.
  const returnTo = '/';

  const loginMutation = useMutation({
    mutationFn: () => authLogin(email.trim().toLowerCase(), password),
    onSuccess: ({ token, user }) => {
      setAuth(token, user);
      navigate(returnTo, { replace: true });
    },
    onError: (err) => {
      setError(err?.response?.data?.detail || 'Login failed');
    },
  });

  const registerMutation = useMutation({
    mutationFn: () =>
      authRegister(email.trim().toLowerCase(), password, {
        bankroll: userProfile.bankroll,
        risk_tolerance: userProfile.riskTolerance,
        experience_level: userProfile.experienceLevel,
        region: userProfile.region,
      }),
    onSuccess: ({ token, user }) => {
      setAuth(token, user);
      navigate(returnTo, { replace: true });
    },
    onError: (err) => {
      setError(err?.response?.data?.detail || 'Registration failed');
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    if (tab === 'register') {
      if (password !== confirm) {
        setError('Passwords do not match');
        return;
      }
      registerMutation.mutate();
    } else {
      loginMutation.mutate();
    }
  };

  const isPending = loginMutation.isPending || registerMutation.isPending;

  return (
    <div>
      <PageHeader
        title={tab === 'login' ? 'SIGN IN' : 'CREATE ACCOUNT'}
        subtitle="Save your bets and profile across devices"
      />

      {/* Tab toggle */}
      <div style={{
        display: 'flex',
        margin: '0 16px 24px',
        background: 'var(--bg-elevated)',
        borderRadius: 'var(--radius-md)',
        padding: 4,
        gap: 4,
      }}>
        {['login', 'register'].map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError(''); }}
            style={{
              flex: 1,
              padding: '9px 0',
              borderRadius: 8,
              border: 'none',
              background: tab === t ? 'var(--bg-card)' : 'transparent',
              color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)',
              fontFamily: 'var(--font-body)',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: tab === t ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
            }}
          >
            {t === 'login' ? 'Sign In' : 'Register'}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} style={{ padding: '0 16px' }}>
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            autoComplete="email"
            style={{ width: '100%', padding: '11px 14px', fontSize: 14 }}
          />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={tab === 'register' ? 'Minimum 8 characters' : 'Your password'}
            required
            autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
            style={{ width: '100%', padding: '11px 14px', fontSize: 14 }}
          />
        </div>

        {tab === 'register' && (
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
              Confirm Password
            </label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Re-enter password"
              required
              autoComplete="new-password"
              style={{ width: '100%', padding: '11px 14px', fontSize: 14 }}
            />
          </div>
        )}

        {error && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(239,68,68,0.1)',
            borderRadius: 'var(--radius-md)',
            borderLeft: '2px solid var(--accent-red-bright)',
            fontSize: 13,
            color: 'var(--accent-red-bright)',
            marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        {tab === 'register' && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(201,162,39,0.08)',
            border: '1px solid var(--border-gold)',
            borderRadius: 'var(--radius-md)',
            fontSize: 12,
            color: 'var(--text-secondary)',
            marginBottom: 16,
            lineHeight: 1.5,
          }}>
            Your current profile settings (bankroll, risk tolerance, experience) will be imported from this device.
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={isPending}
          style={{ width: '100%', padding: '13px 0', fontSize: 14, fontWeight: 700 }}
        >
          {isPending
            ? (tab === 'login' ? 'Signing in…' : 'Creating account…')
            : (tab === 'login' ? 'Sign In' : 'Create Account')}
        </button>
      </form>
    </div>
  );
}
