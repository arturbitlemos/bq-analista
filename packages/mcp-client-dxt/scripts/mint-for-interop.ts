import { issueTokens } from '../src/jwt.js';

const [email, secret, issuer, accessTtl, refreshTtl] = process.argv.slice(2);
const pair = issueTokens({
  email,
  secret,
  issuer,
  accessTtlS: parseInt(accessTtl, 10),
  refreshTtlS: parseInt(refreshTtl, 10),
});
console.log(JSON.stringify(pair));
