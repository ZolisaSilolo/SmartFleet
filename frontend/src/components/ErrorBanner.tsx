import React from 'react';

export const ErrorBanner: React.FC<{ message: string | null }> = ({ message }) =>
  message ? (
    <p role="alert" className="text-sm rounded-lg bg-rose-50 text-rose-800 border border-rose-200 px-3 py-2">
      {message}
    </p>
  ) : null;
