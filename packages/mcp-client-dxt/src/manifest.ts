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

export async function fetchManifest(portalUrl: string): Promise<Manifest> {
  const res = await fetch(`${portalUrl}/api/mcp/agents`);
  if (!res.ok) throw new Error(`manifest fetch failed: ${res.status}`);
  return (await res.json()) as Manifest;
}
