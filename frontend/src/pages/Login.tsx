import React, { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { signIn, SignInStep } from '../services/auth';

type Step = Exclude<SignInStep, { type: 'success' }>;

function describe(error: unknown): string {
  const code = (error as { code?: string; name?: string })?.code ?? (error as { name?: string })?.name;
  switch (code) {
    case 'NotAuthorizedException':
      return 'Incorrect email or password.';
    case 'CodeMismatchException':
    case 'EnableSoftwareTokenMFAException':
      return 'That code is not correct. Check your authenticator app and try again.';
    case 'InvalidPasswordException':
      return 'The new password does not meet the policy (12+ characters with upper, lower, number and symbol).';
    case 'PasswordResetRequiredException':
      return 'A password reset is required. Contact your administrator.';
    case 'TooManyRequestsException':
    case 'LimitExceededException':
      return 'Too many attempts. Please wait a moment and try again.';
    default:
      return 'Sign-in failed. Please try again or contact your administrator.';
  }
}

const inputClass = 'w-full px-3 py-2.5 text-sm rounded-lg border border-slate-300 focus:ring-2 focus:ring-emerald-500 focus:outline-none';

export const Login: React.FC = () => {
  const { refresh } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [secondary, setSecondary] = useState('');
  const [step, setStep] = useState<Step | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const advance = async (action: () => Promise<SignInStep>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await action();
      if (next.type === 'success') {
        await refresh();
      } else {
        setStep(next);
        setSecondary('');
      }
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!step) return void advance(() => signIn(email.trim().toLowerCase(), password));
    return void advance(() => step.submit(secondary.trim()));
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 space-y-5" aria-label="Sign in">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center font-black text-slate-950 text-xl">SF</div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">SmartFleet</h1>
            <p className="text-xs text-slate-500">Sign in to your fleet</p>
          </div>
        </div>

        {error && (
          <p role="alert" className="text-sm rounded-lg bg-rose-50 text-rose-800 border border-rose-200 px-3 py-2">
            {error}
          </p>
        )}

        {!step && (
          <>
            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-slate-700 mb-1">Email</label>
              <input id="email" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-slate-700 mb-1">Password</label>
              <input id="password" type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
            </div>
          </>
        )}

        {step?.type === 'newPasswordRequired' && (
          <div>
            <p className="text-sm text-slate-600 mb-3">Your administrator issued a temporary password. Choose a new one (12+ characters, upper and lower case, a number and a symbol).</p>
            <label htmlFor="newPassword" className="block text-xs font-semibold text-slate-700 mb-1">New password</label>
            <input id="newPassword" type="password" required minLength={12} autoComplete="new-password" value={secondary} onChange={(e) => setSecondary(e.target.value)} className={inputClass} />
          </div>
        )}

        {step?.type === 'mfaSetup' && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600 flex items-start space-x-2">
              <ShieldCheck className="w-4 h-4 mt-0.5 text-emerald-600 shrink-0" />
              <span>Multi-factor authentication is required. In your authenticator app choose &quot;enter a setup key&quot; and add this key, then enter the 6-digit code.</span>
            </p>
            <code className="block break-all rounded-lg bg-slate-100 border border-slate-200 px-3 py-2 text-xs select-all" data-testid="mfa-secret">{step.secretCode}</code>
            <label htmlFor="code" className="block text-xs font-semibold text-slate-700 mb-1">6-digit code</label>
            <input id="code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoComplete="one-time-code" value={secondary} onChange={(e) => setSecondary(e.target.value)} className={inputClass} />
          </div>
        )}

        {step?.type === 'totpRequired' && (
          <div>
            <label htmlFor="totp" className="block text-xs font-semibold text-slate-700 mb-1">Authenticator code</label>
            <input id="totp" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoComplete="one-time-code" value={secondary} onChange={(e) => setSecondary(e.target.value)} className={inputClass} />
          </div>
        )}

        <button type="submit" disabled={busy} className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-semibold">
          {busy ? 'Please wait...' : step ? 'Continue' : 'Sign in'}
        </button>
        <p className="text-xs text-slate-400 text-center">Accounts are created by your fleet administrator. There is no self-registration.</p>
      </form>
    </div>
  );
};
