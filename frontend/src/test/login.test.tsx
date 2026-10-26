import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const refresh = vi.fn();
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ refresh }) }));
vi.mock('../services/auth', () => ({ signIn: vi.fn() }));

import { Login } from '../pages/Login';
import { signIn } from '../services/auth';

describe('Login', () => {
  beforeEach(() => {
    refresh.mockReset();
    vi.mocked(signIn).mockReset();
  });

  it('completes a plain sign-in and refreshes the session', async () => {
    vi.mocked(signIn).mockResolvedValue({ type: 'success' });
    render(<Login />);
    await userEvent.type(screen.getByLabelText('Email'), ' Driver@Example.co.za ');
    await userEvent.type(screen.getByLabelText('Password'), 'a-long-password');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(signIn).toHaveBeenCalledWith('driver@example.co.za', 'a-long-password');
  });

  it('walks a new user through temporary password, MFA enrolment and success', async () => {
    const verify = vi.fn().mockResolvedValue({ type: 'success' });
    const setupMfa = vi.fn().mockResolvedValue({ type: 'mfaSetup', secretCode: 'JBSWY3DPEHPK3PXP', otpauthUri: 'otpauth://x', submit: verify });
    vi.mocked(signIn).mockResolvedValue({ type: 'newPasswordRequired', submit: setupMfa });
    render(<Login />);
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.co.za');
    await userEvent.type(screen.getByLabelText('Password'), 'Temp#Passw0rd!');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await userEvent.type(await screen.findByLabelText('New password'), 'Str0ng&LongPassword');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(setupMfa).toHaveBeenCalledWith('Str0ng&LongPassword');

    expect(await screen.findByTestId('mfa-secret')).toHaveTextContent('JBSWY3DPEHPK3PXP');
    await userEvent.type(screen.getByLabelText('6-digit code'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(verify).toHaveBeenCalledWith('123456');
  });

  it('shows a safe message and stays on the form when credentials are wrong', async () => {
    vi.mocked(signIn).mockRejectedValue({ name: 'NotAuthorizedException' });
    render(<Login />);
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.co');
    await userEvent.type(screen.getByLabelText('Password'), 'wrongwrongwrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.');
    expect(refresh).not.toHaveBeenCalled();
  });
});
