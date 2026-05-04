const { getSql } = require('../_helpers/db')
const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')
const { isAdmin } = require('../_helpers/adminAuth')

async function handleAnalytics(res) {
  const sql = getSql()

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

async function handleBqStats(res, days) {
  const sql = getSql()

  const [totals, byUser, byDay, recentErrors, lastSeenByAgent] = await Promise.all([
    sql`
      SELECT COUNT(*)                                                     AS total_calls,
             SUM(CASE WHEN result = 'error' THEN 1 ELSE 0 END)           AS total_errors,
             SUM(bytes_scanned)                                           AS total_bytes_scanned,
             COUNT(DISTINCT exec_email)                                   AS distinct_users
      FROM bq_audit
      WHERE ts >= NOW() - make_interval(days => ${days})
    `.catch(() => null),

    sql`
      SELECT exec_email,
             COUNT(*)                                              AS total_calls,
             SUM(CASE WHEN result = 'error' THEN 1 ELSE 0 END)   AS errors,
             SUM(bytes_scanned)                                   AS total_bytes,
             ROUND(AVG(duration_ms))                             AS avg_duration_ms,
             MODE() WITHIN GROUP (ORDER BY agent)                AS top_agent
      FROM bq_audit
      WHERE ts >= NOW() - make_interval(days => ${days})
      GROUP BY exec_email
      ORDER BY total_calls DESC
    `.catch(() => null),

    sql`
      SELECT DATE_TRUNC('day', ts)::date AS day,
             exec_email,
             COUNT(*)                   AS n
      FROM bq_audit
      WHERE ts >= NOW() - make_interval(days => ${days})
      GROUP BY 1, 2
      ORDER BY 1
    `.catch(() => null),

    sql`
      SELECT ts, exec_email, agent, tool,
             LEFT(sql, 200) AS sql_preview,
             error, bytes_scanned
      FROM bq_audit
      WHERE result = 'error'
        AND ts >= NOW() - make_interval(days => ${days})
      ORDER BY ts DESC
      LIMIT 20
    `.catch(() => null),

    sql`
      SELECT agent, MAX(ts) AS last_seen
      FROM bq_audit
      GROUP BY agent
      ORDER BY agent
    `.catch(() => null),
  ])

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({
    totals: totals?.[0] ?? {},
    by_user: byUser ?? [],
    by_day: byDay ?? [],
    recent_errors: recentErrors ?? [],
    last_seen_by_agent: lastSeenByAgent ?? [],
  })
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })
  if (!isAdmin(email, process.env.ADMIN_EMAILS)) return res.status(403).json({ error: 'forbidden' })

  const { action } = req.query
  if (action === 'analytics') return handleAnalytics(res)
  if (action === 'bq-stats') {
    const days = Math.max(1, Math.min(90, parseInt(req.query.days, 10) || 30))
    return handleBqStats(res, days)
  }
  return res.status(404).json({ error: 'not found' })
}
