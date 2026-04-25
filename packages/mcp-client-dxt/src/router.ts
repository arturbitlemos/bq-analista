import type { Agent, ToolDef } from './manifest.js';

function slug(name: string): string {
  return name.replace(/-/g, '_');
}

export function prefixedTool(agentName: string, tool: string): string {
  return `${slug(agentName)}__${tool}`;
}

export function listPrefixedTools(agents: Agent[]): { name: string; agent: Agent; tool: ToolDef }[] {
  const result: { name: string; agent: Agent; tool: ToolDef }[] = [];
  for (const agent of agents) {
    for (const tool of agent.tools) {
      result.push({ name: prefixedTool(agent.name, tool.name), agent, tool });
    }
  }
  return result;
}

export function resolveRoute(toolName: string, agents: Agent[]): { agent: Agent; tool: string } | null {
  const idx = toolName.indexOf('__');
  if (idx < 0) return null;
  const agentSlug = toolName.slice(0, idx);
  const tool = toolName.slice(idx + 2);
  const agent = agents.find((a) => slug(a.name) === agentSlug);
  if (!agent) return null;
  if (!agent.tools.some((t) => t.name === tool)) return null;
  return { agent, tool };
}
