import jwt, { type JwtPayload, type SignOptions, type VerifyOptions } from 'jsonwebtoken';

export type TokenKind = 'access' | 'refresh';

export interface IssueParams {
  email: string;
  secret: string;
  issuer: string;
  accessTtlS: number;
  refreshTtlS: number;
}

export interface TokenPair {
  access: string;
  refresh: string;
  accessExp: number;
  refreshExp: number;
}

export interface TokenClaims extends JwtPayload {
  email: string;
  kind: TokenKind;
  iss: string;
  sub: string;
  iat: number;
  exp: number;
}

const MIN_SECRET_BYTES = 32;

function checkSecret(secret: string): void {
  if (Buffer.byteLength(secret, 'utf8') < MIN_SECRET_BYTES) {
    throw new Error(`JWT secret must be at least ${MIN_SECRET_BYTES} bytes for HS256`);
  }
}

function encode(kind: TokenKind, params: { email: string; secret: string; issuer: string; ttl: number }): { token: string; exp: number } {
  const now = Math.floor(Date.now() / 1000);
  const exp = now + params.ttl;
  const payload = {
    iss: params.issuer,
    sub: params.email,
    email: params.email,
    kind,
    iat: now,
    exp,
  };
  const options: SignOptions = { algorithm: 'HS256', noTimestamp: true };
  const token = jwt.sign(payload, params.secret, options);
  return { token, exp };
}

export function issueTokens(params: IssueParams): TokenPair {
  checkSecret(params.secret);
  const access = encode('access', { email: params.email, secret: params.secret, issuer: params.issuer, ttl: params.accessTtlS });
  const refresh = encode('refresh', { email: params.email, secret: params.secret, issuer: params.issuer, ttl: params.refreshTtlS });
  return { access: access.token, refresh: refresh.token, accessExp: access.exp, refreshExp: refresh.exp };
}

export function decodeToken(token: string, secret: string, issuer: string): TokenClaims {
  checkSecret(secret);
  const options: VerifyOptions = { algorithms: ['HS256'], issuer };
  const claims = jwt.verify(token, secret, options);
  if (typeof claims === 'string') throw new Error('unexpected string claims');
  return claims as TokenClaims;
}

export function refreshAccess(refreshToken: string, secret: string, issuer: string, accessTtlS: number): string {
  const claims = decodeToken(refreshToken, secret, issuer);
  if (claims.kind !== 'refresh') throw new Error('not a refresh token');
  const result = encode('access', { email: claims.email, secret, issuer, ttl: accessTtlS });
  return result.token;
}
