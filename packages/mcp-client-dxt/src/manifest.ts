export interface ToolDef {
  name: string;
  inputSchema: Record<string, unknown>;
}

export interface Agent {
  name: string;
  label: string;
  url: string;
  tools: ToolDef[];
}

export interface Manifest {
  min_dxt_version: string;
  agents: Agent[];
}

const GENERIC_SCHEMA: Record<string, unknown> = { type: 'object', additionalProperties: true };

// Portal ≤1.0.5 serves tools as string[]; ≥1.0.6 serves ToolDef[].
// Normalise either format so the DXT works regardless of portal version.
function normaliseTools(raw: Array<string | ToolDef>): ToolDef[] {
  return raw.map((t) =>
    typeof t === 'string' ? { name: t, inputSchema: GENERIC_SCHEMA } : t,
  );
}

export async function fetchManifest(portalUrl: string): Promise<Manifest> {
  const res = await fetch(`${portalUrl}/api/mcp/agents`);
  if (!res.ok) throw new Error(`manifest fetch failed: ${res.status}`);
  const raw = (await res.json()) as {
    min_dxt_version: string;
    agents: Array<{ name: string; label: string; url: string; tools: Array<string | ToolDef> }>;
  };
  return {
    min_dxt_version: raw.min_dxt_version,
    agents: raw.agents.map((a) => ({ ...a, tools: normaliseTools(a.tools) })),
  };
}
