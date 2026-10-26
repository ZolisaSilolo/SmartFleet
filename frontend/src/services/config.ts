/**
 * Runtime configuration. All values are injected at build time from the deployed stack outputs (see the CI workflow);
 * there are no defaults pointing at any environment, so a mis-built bundle fails loudly instead of calling the wrong API.
 */
function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing required build-time setting ${name}`);
  }
  return value;
}

export const config = {
  /** Same-origin API path served by CloudFront (/api/* -> HTTP API). */
  apiBase: import.meta.env.VITE_API_BASE ?? '/api',
  get userPoolId(): string {
    return required('VITE_COGNITO_USER_POOL_ID', import.meta.env.VITE_COGNITO_USER_POOL_ID);
  },
  get clientId(): string {
    return required('VITE_COGNITO_CLIENT_ID', import.meta.env.VITE_COGNITO_CLIENT_ID);
  },
};
