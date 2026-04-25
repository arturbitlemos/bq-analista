function b64urlToBuffer(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  return Buffer.from(str, 'base64');
}

function b64urlToString(str) {
  return b64urlToBuffer(str).toString('utf8');
}

module.exports = { b64urlToBuffer, b64urlToString };
