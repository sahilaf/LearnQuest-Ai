/**
 * ForgotPassword - OWNER: Member 3. See plan.md §8.4.
 *
 * Supabase password reset email.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { KeyRound, Sparkles, AlertCircle, CheckCircle2, ArrowLeft } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { Button, Card, Input } from '../../components/ui';

export default function ForgotPassword() {
  const { resetPassword, devMode } = useAuth();

  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    setLoading(true);
    try {
      const err = await resetPassword(email.trim());
      if (err) {
        setError(typeof err === 'string' ? err : err.message || 'Failed to send reset email.');
      } else {
        setSent(true);
      }
    } catch (exc) {
      setError(exc.message || 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-raised px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-primary-600 text-white shadow-md">
            <Sparkles className="h-7 w-7" />
          </div>
          <h2 className="mt-4 text-3xl font-bold tracking-tight text-ink">
            Reset your password
          </h2>
          <p className="mt-2 text-sm text-body">
            Enter your email and we'll send you instructions to reset your password
          </p>
        </div>

        <Card className="shadow-lg">
          {devMode && (
            <div className="mb-4 rounded-xl bg-medium-bg p-3 text-xs text-medium-fg">
              <span className="font-semibold">Dev Mode Active:</span> In dev mode without Supabase,
              password reset emails are simulated.
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-xl bg-hard-bg p-3 text-sm text-hard-fg">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {sent ? (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-easy-bg text-easy-fg">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-ink">
                Check your inbox
              </h3>
              <p className="text-sm text-body">
                We sent a password reset link to <span className="font-medium">{email}</span>.
              </p>
              <div className="pt-2">
                <Link to="/login">
                  <Button variant="secondary" className="w-full justify-center">
                    <ArrowLeft className="h-4 w-4" />
                    Back to sign in
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Email address"
                type="email"
                name="email"
                autoComplete="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />

              <Button
                type="submit"
                variant="primary"
                loading={loading}
                className="w-full justify-center py-2.5"
              >
                <KeyRound className="h-4 w-4" />
                Send reset link
              </Button>

              <div className="pt-2 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-300 hover:text-primary-300"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back to sign in
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
