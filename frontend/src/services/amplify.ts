import { Amplify } from '@aws-amplify/core';
import type { KeyValueStorageInterface } from '@aws-amplify/core';
import { cognitoUserPoolsTokenProvider } from '@aws-amplify/auth/cognito';
import { config } from './config';

/**
 * Promise-returning adapter over the synchronous Web Storage API. Amplify's token provider expects an
 * async KeyValueStorageInterface; sessionStorage is synchronous, so we wrap each call. We deliberately
 * back it with sessionStorage (not localStorage) so tokens do not outlive the browser tab.
 */
const sessionTokenStorage: KeyValueStorageInterface = {
  setItem: (key, value) => Promise.resolve(window.sessionStorage.setItem(key, value)),
  getItem: (key) => Promise.resolve(window.sessionStorage.getItem(key)),
  removeItem: (key) => Promise.resolve(window.sessionStorage.removeItem(key)),
  clear: () => Promise.resolve(window.sessionStorage.clear()),
};

/**
 * Configure the Amplify client auth library once, at startup, from the build-time stack outputs.
 *
 * Token storage is pinned to sessionStorage (Amplify defaults to localStorage): tokens are cleared
 * when the tab closes, limiting the lifetime of a token stolen via XSS. The app client is a PUBLIC
 * client (no secret) using the authorization-code/SRP flow, as required for a browser SPA.
 */
let configured = false;

export function configureAmplify(): void {
  if (configured) return;

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.clientId,
      },
    },
  });

  // Keep refresh/ID/access tokens in sessionStorage rather than the Amplify default (localStorage).
  cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionTokenStorage);

  configured = true;
}
