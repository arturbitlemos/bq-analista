import { PublicClientApplication, InteractionRequiredAuthError } from '@azure/msal-browser'

let msalInstance = null

async function initMsal() {
  const res = await fetch('/api/config')
  if (!res.ok) throw new Error('Failed to load Azure config')

  const { clientId, tenantId } = await res.json()

  msalInstance = new PublicClientApplication({
    auth: {
      clientId,
      authority: `https://login.microsoftonline.com/${tenantId}`,
      redirectUri: window.location.origin
    },
    cache: { cacheLocation: 'sessionStorage' }
  })

  return msalInstance
}

export { initMsal, InteractionRequiredAuthError }
