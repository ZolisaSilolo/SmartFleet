import {
  confirmSignIn,
  fetchAuthSession,
  signIn as amplifySignIn,
  signOut as amplifySignOut,
  type ConfirmSignInInput,
} from '@aws-amplify/auth';

/**
 * Authentication is handled by the Amplify client auth library (@aws-amplify/auth) talking to the
 * SmartFleet Cognito user pool. SRP is the default first factor; the pool enforces TOTP MFA.
 *
 * Tokens live in sessionStorage (configured in ./amplify.ts), not localStorage, so a stolen token
 * dies with the tab; the CloudFront CSP forbids inline/remote scripts, which is the primary XSS defence.
 *
 * This module exposes a small, stable surface (signIn/getIdToken/getIdentity/signOut) so the rest of
 * the app never imports Amplify directly and the multi-step challenge flow stays in one place.
 */

/** A step in the interactive sign-in flow. Mirrors Amplify's nextStep as a closed, app-specific union. */
export type SignInStep =
  | { type: 'success' }
  | { type: 'newPasswordRequired'; submit: (newPassword: string) => Promise<SignInStep> }
  | { type: 'totpRequired'; submit: (code: string) => Promise<SignInStep> }
  | { type: 'mfaSetup'; secretCode: string; otpauthUri: string; submit: (code: string) => Promise<SignInStep> };

/** An error Amplify sometimes raises when a stale sign-in is still in progress; we reset and surface it. */
const ALREADY_SIGNED_IN = 'UserAlreadyAuthenticatedException';

/** Translate an Amplify sign-in/confirm result into the next SignInStep the UI should render. */
function toStep(step: { signInStep: string; totpSetupDetails?: { sharedSecret: string; getSetupUri: (appName: string, accountName?: string) => URL } }, email: string): SignInStep {
  switch (step.signInStep) {
    case 'DONE':
      return { type: 'success' };

    case 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED':
      // Only the new password is sent; the tenant attribute is immutable and never client-writable.
      return { type: 'newPasswordRequired', submit: (newPassword) => confirm({ challengeResponse: newPassword }, email) };

    case 'CONTINUE_SIGN_IN_WITH_TOTP_SETUP': {
      const details = step.totpSetupDetails;
      if (!details) throw new Error('Cognito did not return TOTP setup details');
      const secretCode = details.sharedSecret;
      // getSetupUri builds the otpauth:// URI the user adds to their authenticator (issuer + account).
      const otpauthUri = details.getSetupUri('SmartFleet', email).toString();
      return { type: 'mfaSetup', secretCode, otpauthUri, submit: (code) => confirm({ challengeResponse: code }, email) };
    }

    case 'CONFIRM_SIGN_IN_WITH_TOTP_CODE':
      return { type: 'totpRequired', submit: (code) => confirm({ challengeResponse: code }, email) };

    // Every other challenge (SMS/email OTP, password re-prompt, MFA selection, custom) is not enabled on
    // this pool. Surfacing rather than silently stalling makes a pool misconfiguration fail loudly.
    default:
      throw new Error(`Unsupported sign-in step: ${step.signInStep}`);
  }
}

async function confirm(input: ConfirmSignInInput, email: string): Promise<SignInStep> {
  const { nextStep } = await confirmSignIn(input);
  return toStep(nextStep, email);
}

/** Begin interactive sign-in. Resolves with the first step (success or a challenge to complete). */
export async function signIn(email: string, password: string): Promise<SignInStep> {
  try {
    const { nextStep } = await amplifySignIn({ username: email, password });
    return toStep(nextStep, email);
  } catch (error) {
    // A lingering session (e.g. a reloaded half-finished flow) blocks a fresh sign-in; clear and retry once.
    if ((error as { name?: string })?.name === ALREADY_SIGNED_IN) {
      await amplifySignOut();
      const { nextStep } = await amplifySignIn({ username: email, password });
      return toStep(nextStep, email);
    }
    throw error;
  }
}

/** The ID token (it carries custom:tenantId, which the API requires). Null when signed out. */
export async function getIdToken(): Promise<string | null> {
  try {
    // forceRefresh is omitted: Amplify transparently refreshes an expired ID/access token with the refresh token.
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() ?? null;
  } catch {
    return null;
  }
}

export interface Identity {
  email: string;
  tenantId: string;
}

export async function getIdentity(): Promise<Identity | null> {
  try {
    const session = await fetchAuthSession();
    const payload = session.tokens?.idToken?.payload;
    if (!payload) return null;
    return {
      email: String(payload.email ?? ''),
      // The tenant is a verified, admin-assigned claim on the ID token - never read from client input.
      tenantId: String(payload['custom:tenantId'] ?? ''),
    };
  } catch {
    return null;
  }
}

export async function signOut(): Promise<void> {
  // Global sign-out revokes the refresh token server-side, not just on this device.
  await amplifySignOut({ global: true });
}
