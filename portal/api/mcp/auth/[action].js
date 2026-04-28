// Single Vercel Serverless Function that fans out to the three OAuth-flow
// handlers (start / callback / refresh). Lives here because the Hobby plan
// caps deployments at 12 functions; each handler used to be its own file.
// The actual logic stays in ./_handlers/* (underscore prefix excludes them
// from the function count) so the modules remain testable in isolation.
const start = require('./_handlers/start');
const callback = require('./_handlers/callback');
const refresh = require('./_handlers/refresh');

const ROUTES = { start, callback, refresh };

module.exports = function handler(req, res) {
  const action = (req.query?.action || '').toString();
  const fn = ROUTES[action];
  if (!fn) return res.status(404).send(`unknown auth action: ${action}`);
  return fn(req, res);
};
