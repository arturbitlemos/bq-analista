const { neon } = require('@neondatabase/serverless')

let _sql = null
function getSql() {
  if (!_sql) {
    if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL not set')
    _sql = neon(process.env.DATABASE_URL)
  }
  return _sql
}

module.exports = { getSql }
