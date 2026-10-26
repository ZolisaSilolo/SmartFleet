import { useCallback, useState } from 'react';
import { ApiRequestError } from '../services/http';

export function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.code === 'VALIDATION_ERROR') return 'Some of the information entered is not valid. Please check the form and try again.';
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

/** Runs an async action, tracking busy/error state. Resolves true on success, false on failure (never throws). */
export function useAsync() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (action: () => Promise<unknown>): Promise<boolean> => {
    setBusy(true);
    setError(null);
    try {
      await action();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  return { run, error, busy, setError };
}
