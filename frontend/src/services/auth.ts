import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
  CognitoUserSession,
  IAuthenticationCallback,
} from 'amazon-cognito-identity-js';
import { config } from './config';

/**
 * Cognito SRP sign-in. Tokens live in sessionStorage (cleared when the tab closes) rather than localStorage to limit the
 * lifetime of a stolen token; the CloudFront CSP forbids inline/remote scripts, which is the primary XSS defence.
 */
let pool: CognitoUserPool | null = null;

function getPool(): CognitoUserPool {
  if (!pool) {
    pool = new CognitoUserPool({
      UserPoolId: config.userPoolId,
      ClientId: config.clientId,
      Storage: window.sessionStorage,
    });
  }
  return pool;
}

export type SignInStep =
  | { type: 'success' }
  | { type: 'newPasswordRequired'; submit: (newPassword: string) => Promise<SignInStep> }
  | { type: 'totpRequired'; submit: (code: string) => Promise<SignInStep> }
  | { type: 'mfaSetup'; secretCode: string; otpauthUri: string; submit: (code: string) => Promise<SignInStep> };

function callbacksFor(
  user: CognitoUser,
  email: string,
  resolve: (step: SignInStep) => void,
  reject: (err: unknown) => void,
): IAuthenticationCallback {
  // Every challenge response gets a fresh callbacks object, so chained challenges
  // (temporary password -> MFA setup -> TOTP) each resolve the promise of the step that triggered them.
  return {
    onSuccess: () => resolve({ type: 'success' }),
    onFailure: (err: unknown) => reject(err),
    newPasswordRequired: () =>
      resolve({
        type: 'newPasswordRequired',
        // Only the new password is sent: the tenant attribute is immutable and never client-writable.
        submit: (newPassword: string) =>
          new Promise<SignInStep>((res, rej) => user.completeNewPasswordChallenge(newPassword, {}, callbacksFor(user, email, res, rej))),
      }),
    totpRequired: () =>
      resolve({
        type: 'totpRequired',
        submit: (code: string) =>
          new Promise<SignInStep>((res, rej) => user.sendMFACode(code, callbacksFor(user, email, res, rej), 'SOFTWARE_TOKEN_MFA')),
      }),
    mfaSetup: () => {
      user.associateSoftwareToken({
        associateSecretCode: (secretCode: string) =>
          resolve({
            type: 'mfaSetup',
            secretCode,
            otpauthUri: `otpauth://totp/SmartFleet:${encodeURIComponent(email)}?secret=${secretCode}&issuer=SmartFleet`,
            submit: (code: string) =>
              new Promise<SignInStep>((res, rej) =>
                user.verifySoftwareToken(code, 'SmartFleet authenticator', {
                  onSuccess: () => res({ type: 'success' }),
                  onFailure: (err: unknown) => rej(err),
                }),
              ),
          }),
        onFailure: (err: unknown) => reject(err),
      });
    },
  };
}

export function signIn(email: string, password: string): Promise<SignInStep> {
  const user = new CognitoUser({ Username: email, Pool: getPool(), Storage: window.sessionStorage });
  const details = new AuthenticationDetails({ Username: email, Password: password });
  return new Promise<SignInStep>((resolve, reject) => user.authenticateUser(details, callbacksFor(user, email, resolve, reject)));
}
function currentSession(): Promise<CognitoUserSession | null> {
  const user = getPool().getCurrentUser();
  if (!user) return Promise.resolve(null);
  return new Promise((resolve) => {
    // getSession transparently refreshes an expired access/ID token with the refresh token.
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      resolve(!err && session && session.isValid() ? session : null);
    });
  });
}

/** The ID token (it carries custom:tenantId, which the API requires). Null when signed out. */
export async function getIdToken(): Promise<string | null> {
  const session = await currentSession();
  return session ? session.getIdToken().getJwtToken() : null;
}

export interface Identity {
  email: string;
  tenantId: string;
}

export async function getIdentity(): Promise<Identity | null> {
  const session = await currentSession();
  if (!session) return null;
  const payload = session.getIdToken().payload as Record<string, string>;
  return { email: payload.email, tenantId: payload['custom:tenantId'] ?? '' };
}

export function signOut(): Promise<void> {
  const user = getPool().getCurrentUser();
  const clear = () => {
    user?.signOut();
    window.sessionStorage.clear();
  };
  if (!user) {
    clear();
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const done = () => {
      clear();
      resolve();
    };
    // Global sign-out revokes the refresh token server-side, not just locally.
    user.getSession((err: Error | null) => {
      if (err) return done();
      user.globalSignOut({ onSuccess: done, onFailure: done });
    });
  });
}