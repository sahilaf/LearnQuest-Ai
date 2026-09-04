/**
 * Register - OWNER: Member 3. See plan.md §8.4.
 *
 * Account creation via Supabase Auth.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { UserPlus, Sparkles, AlertCircle } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { Button, Card, Input } from '../../components/ui';

export default function Register() {
  const navigate = useNavigate();
  const { register, loginWithGoogle, isAuthenticated, devMode } = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState(null);

  if (isAuthenticated) {
    navigate('/dashboard', { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!fullName.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (!email.trim()) {
      setError('Please enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const err = await register(email.trim(), password, fullName.trim());
      if (err) {
        setError(typeof err === 'string' ? err : err.message || 'Registration failed.');
      } else {
        navigate('/dashboard', { replace: true });
      }
    } catch (exc) {
      setError(exc.message || 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setGoogleLoading(true);
    try {
      const err = await loginWithGoogle();
      if (err) {
        setError(typeof err === 'string' ? err : err.message || 'Google sign-up failed.');
      } else if (devMode) {
        navigate('/dashboard', { replace: true });
      }
    } catch (exc) {
      setError(exc.message || 'Failed to initialize Google authentication.');
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-950 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-md">
            <Sparkles className="h-7 w-7" />
          </div>
          <h2 className="mt-4 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
            Create an account
          </h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            Start your adaptive learning adventure with LearnQuest AI
          </p>
        </div>

        <Card className="shadow-lg">
          {devMode && (
            <div className="mb-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              <span className="font-semibold">Dev Mode Active:</span> Supabase keys are not set.
              Registration will simulate an account using local dev mode.
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full name"
              type="text"
              name="fullName"
              required
              placeholder="Sarah Chen"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />

            <Input
              label="Email address"
              type="email"
              name="email"
              autoComplete="email"
              required
              placeholder="sarah@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            <div>
              <label className="mb-1.5 block text-sm font-medium">Password</label>
              <input
                type="password"
                name="password"
                autoComplete="new-password"
                required
                placeholder="At least 6 characters"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm transition-colors dark:border-slate-700 dark:bg-slate-800"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium">Confirm password</label>
              <input
                type="password"
                name="confirmPassword"
                autoComplete="new-password"
                required
                placeholder="Repeat your password"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm transition-colors dark:border-slate-700 dark:bg-slate-800"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              loading={loading}
              className="w-full justify-center py-2.5"
            >
              <UserPlus className="h-4 w-4" />
              Create account
            </Button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200 dark:border-slate-800" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-slate-500 dark:bg-slate-900">Or sign up with</span>
            </div>
          </div>

          <Button
            type="button"
            variant="secondary"
            loading={googleLoading}
            onClick={handleGoogleSignIn}
            className="w-full justify-center py-2.5"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24">
              <path
                fill="#EA4335"
                d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"
              />
              <path
                fill="#4285F4"
                d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z"
              />
              <path
                fill="#FBBC05"
                d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.3 0 15.2c0 2.8.7 5.5 1.9 7.8l3.7-2.9z"
              />
              <path
                fill="#34A853"
                d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16.5C3.7 20.2 7.5 23.5 12 23.5z"
              />
            </svg>
            Sign up with Google
          </Button>

          <p className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">
            Already have an account?{' '}
            <Link
              to="/login"
              className="font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
            >
              Sign in
            </Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
