/**
 * Returns true if email is in the ADMIN_EMAILS env var list.
 * adminEmailsEnv: comma-separated string, e.g. "a@soma.com,b@soma.com"
 * Comparison is case-insensitive; extra whitespace around emails is trimmed.
 */
function isAdmin(email, adminEmailsEnv) {
  if (!email || !adminEmailsEnv) return false
  const list = adminEmailsEnv.split(',').map(e => e.trim().toLowerCase()).filter(Boolean)
  return list.includes(email.toLowerCase().trim())
}

module.exports = { isAdmin }
