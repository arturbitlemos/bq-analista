import { describe, it, expect } from 'vitest';
import { credentialsPath, logsDir } from '../src/paths';
import os from 'node:os';
import path from 'node:path';

describe('paths', () => {
  it('credentialsPath fica em ~/.mcp/credentials.json', () => {
    expect(credentialsPath()).toBe(path.join(os.homedir(), '.mcp', 'credentials.json'));
  });
  it('logsDir fica em ~/.mcp/logs', () => {
    expect(logsDir()).toBe(path.join(os.homedir(), '.mcp', 'logs'));
  });
});
