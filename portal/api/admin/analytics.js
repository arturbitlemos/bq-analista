const { getSql } = require('../_helpers/db')
const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')
const { isAdmin } = require('../_helpers/adminAuth')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })
  if (!isAdmin(email, process.env.ADMIN_EMAILS)) return res.status(403).json({ error: 'forbidden' })

  const sql = getSql()

  // Run all queries in parallel; individual failures return null so the page
  // still renders partial data rather than a full 500.
  const [summary, byActionByDay, topUsers, topAnalyses, recentActivity] = await Promise.all([
    sql`
      SELECT
        COUNT(*) FILTER (WHERE action = 'publish')      AS total_publishes,
        COUNT(*) FILTER (WHERE action = 'refresh')      AS total_refreshes,
        COUNT(*) FILTER (WHERE action = 'share')        AS total_shares,
        COUNT(*) FILTER (WHERE action = 'archive')      AS total_archives,
        COUNT(*) FILTER (WHERE action = 'login_failed') AS total_login_failures,
        COUNT(DISTINCT actor_email)                      AS distinct_users,
        COUNT(*)                                         AS total_events
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '30 days'
    `.catch(() => null),

    sql`
      SELECT
        DATE_TRUNC('day', occurred_at)::date AS day,
        action,
        COUNT(*) AS n
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '14 days'
        AND action IN ('publish', 'refresh', 'share', 'archive')
      GROUP BY 1, 2
      ORDER BY 1 ASC, 2
    `.catch(() => null),

    sql`
      SELECT actor_email, COUNT(*) AS n
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '30 days'
        AND action != 'login_failed'
      GROUP BY actor_email
      ORDER BY n DESC
      LIMIT 10
    `.catch(() => null),

    sql`
      SELECT al.analysis_id, COUNT(*) AS n, a.title
      FROM audit_log al
      LEFT JOIN analyses a ON a.id = al.analysis_id
      WHERE al.occurred_at >= NOW() - INTERVAL '30 days'
        AND al.action IN ('refresh', 'share')
        AND al.analysis_id IS NOT NULL
      GROUP BY al.analysis_id, a.title
      ORDER BY n DESC
      LIMIT 10
    `.catch(() => null),

    sql`
      SELECT occurred_at, actor_email, action, analysis_id
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '30 days'
      ORDER BY occurred_at DESC
      LIMIT 50
    `.catch(() => null),
  ])

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({
    summary: summary?.[0] ?? null,
    by_action_by_day: byActionByDay ?? [],
    top_users: topUsers ?? [],
    top_analyses: topAnalyses ?? [],
    recent_activity: recentActivity ?? [],
  })
}
