# Analytics Library — Design Spec
**Date:** 2026-04-17  
**Status:** Approved, ready for implementation

---

## Overview

A shared company analytics platform where analysts run BigQuery analyses locally via Claude Code and publish self-contained HTML dashboards to a Vercel-hosted library. Access is protected by Azure AD SSO. Each analyst's analyses are private by default; they can opt to make individual analyses public to the whole company.

---

## Goals

- Shared `queries/` directory with standard SQL and consistent business rules
- Per-user private analysis publishing + opt-in public sharing
- Azure AD SSO — no separate password management
- No persistent backend to maintain (Edge Middleware + serverless function only)
- Token/rate-limit management delegated to individual Anthropic accounts (local Claude Code per analyst)
- Predictable cost: each analyst pays their own Anthropic usage

---

## Architecture

### Repository Structure

```
/
├── index.html                  ← SPA: Azure AD login + library UI
├── middleware.js               ← Vercel Edge: validates JWT + enforces ownership
├── api/
│   └── auth.js                 ← Vercel serverless: Azure AD OAuth callback
├── vercel.json                 ← routing, edge middleware config, headers
├── analyses/
│   ├── public/                 ← visible to any authenticated user
│   │   └── {analysis-id}.html
│   └── {userOID}/              ← visible only to the owner
│       └── {analysis-id}.html
├── library/
│   ├── public.json             ← index of all public analyses
│   └── {userOID}.json          ← personal index (one writer = zero conflicts)
├── queries/                    ← standard company SQL (reviewed via PR)
│   └── *.sql
├── SKILL.md                    ← Claude Code skill for running + publishing analyses
├── schema.md                   ← living BigQuery schema reference
├── business-rules.md           ← KPI definitions and business logic
└── docs/
    └── superpowers/specs/      ← design documents
```

### Analysis ID Convention

`{brand}-{topic}-{YYYY-MM-DD}` — e.g. `farm-produto-ecomm-2026-04-17`

---

## Authentication

**Provider:** Azure AD (Microsoft Entra ID)  
**Protocol:** OAuth 2.0 / OIDC  
**Library:** `@azure/msal-browser` loaded in `index.html`

**Flow:**
1. User opens Vercel URL → `index.html` checks for valid Azure AD token in sessionStorage
2. If no token → MSAL redirects to Azure AD login page
3. After login → Azure AD returns ID token (JWT) with `oid` claim (userOID)
4. `api/auth.js` handles the OAuth callback, validates token, sets a signed session cookie on the Vercel domain
5. All subsequent requests carry the cookie; Edge Middleware validates it before serving any file

**Required setup (one-time, by platform admin):**
- Register an Azure AD application
- Set redirect URI to `https://{vercel-domain}/api/auth`
- Note the `client_id` and `tenant_id` → add to Vercel environment variables

---

## Access Control

**Vercel Edge Middleware** (`middleware.js`) intercepts every request to `/analyses/*`:

```
Request to /analyses/{segment}/...
  ├── segment = "public"  → allow if JWT is valid (any authenticated user)
  └── segment = {userOID} → allow only if JWT oid claim === segment
                            otherwise → 403
```

Static files are **never** accessible without a valid session cookie. There is no URL guessing — ownership is enforced by the OID claim from Azure AD.

---

## Library Index (no merge conflicts)

Each analyst owns exactly one file: `library/{userOID}.json`

```json
[
  {
    "id": "farm-produto-ecomm-2026-04-17",
    "title": "Top Produtos · Ecommerce",
    "brand": "FARM",
    "period": "11–17 Abr 2026",
    "date": "2026-04-17",
    "description": "Top 10 produtos, categorias e tendência diária.",
    "file": "analyses/{userOID}/farm-produto-ecomm-2026-04-17.html",
    "public": false,
    "tags": ["produto", "ecommerce", "ranking"]
  }
]
```

`library/public.json` mirrors this structure but only contains entries where `public: true`.  
When an analyst makes an analysis public, Claude Code:
1. Copies the HTML to `analyses/public/{id}.html`
2. Adds the entry to `library/public.json`
3. Commits and pushes

`index.html` fetches both `library/{userOID}.json` and `library/public.json` at login and merges them client-side (deduplicating by `id`).

---

## User Flow (browser)

1. Open Vercel URL → Azure AD login (SSO, no separate password)
2. After auth → library loads: own analyses + public analyses, newest first
3. Filter chips: All / by brand / by tag
4. Click a card → analysis opens **inline (iframe)** within the library shell
   - Top bar shows: `← Library  /  {brand} · {title}`
   - Edge Middleware validates session cookie before serving the iframe src
5. Back arrow → returns to library grid (no page reload)

---

## Analyst Workflow (Claude Code local)

**Prerequisites (one-time setup per machine):**
- Claude Code CLI installed and logged in
- `gcloud` CLI installed and authenticated (`gcloud auth application-default login`)
- `bq` CLI available
- Git configured with access to the company repo
- `.env` file in project root with `USER_OID=<azure-ad-object-id>` (analyst finds this in Azure AD portal or by running a helper command)

**Per-analysis workflow (automated by SKILL.md):**
1. Analyst asks Claude Code to run an analysis
2. Claude Code dry-runs, executes BQ queries, generates HTML dashboard
3. Claude Code saves to `analyses/{USER_OID}/{id}.html`
4. Claude Code updates `library/{USER_OID}.json` (appends new entry)
5. Commit + push → Vercel rebuild (~60s) → analysis live at Vercel URL

**To make an analysis public:**
- Analyst tells Claude Code: "torna essa análise pública"
- Claude Code copies HTML to `analyses/public/{id}.html`, adds to `library/public.json`, commits, pushes

---

## Standard Queries (`queries/`)

- All company-standard SQL lives here
- Changes require a PR review (governance)
- Claude Code reads from this directory when building analyses
- Breaking changes to queries must be versioned (e.g., `queries/v2/`)

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Auth | Azure AD SSO | Company SSO, no extra credentials |
| Hosting | Vercel static + Edge Middleware | No persistent backend |
| Motor | Local Claude Code per analyst | Granular permissions, Anthropic manages billing |
| Navigation | Iframe inline | Seamless UX, auth context preserved |
| Privacy | Folder-per-OID + Edge Middleware | Real enforcement, not URL obscurity |
| Conflict avoidance | Per-user library JSON | Single writer per file |

---

## Vercel Configuration (`vercel.json`)

```json
{
  "version": 2,
  "middleware": [{ "src": "/analyses/(.*)" }],
  "functions": {
    "api/auth.js": { "maxDuration": 10 }
  },
  "headers": [
    {
      "source": "/analyses/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "private, no-store" }]
    }
  ]
}
```

---

## Environment Variables (Vercel dashboard)

| Variable | Description |
|---|---|
| `AZURE_CLIENT_ID` | Azure AD app client ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_CLIENT_SECRET` | Azure AD client secret |
| `SESSION_SECRET` | Secret for signing session cookies |

---

## What This Spec Does NOT Cover

- Mobile app or native clients
- Analysis editing after publish (treat as immutable; republish with new date)
- Comments or collaboration on analyses
- Automated BQ scheduling (all analyses are on-demand)
