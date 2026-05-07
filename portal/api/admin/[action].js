const { getSql } = require('../_helpers/db')
const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')
const { isAdmin } = require('../_helpers/adminAuth')
const { mintProxyJwt } = require('../_helpers/proxy_jwt')
const { MANIFEST } = require('../mcp/_helpers/manifest')

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

async function handleBqStats(res, email) {
  let token
  try {
    token = mintProxyJwt(email)
  } catch (err) {
    return res.status(503).json({ error: `JWT proxy: ${err.message}` })
  }

  const agents = MANIFEST.agents

  // Fan-out to all agents in parallel; individual failures are noted but don't crash the response
  const settled = await Promise.allSettled(
    agents.map(agent =>
      fetch(`${agent.url}/api/admin/bq-stats`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(10_000),
      })
        .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
        .then(data => ({ ...data, _agent: agent.name, _ok: true }))
    )
  )

  // Merge across agents
  const byUserMap = {}
  const totals = {}
  const recentErrors = []
  const agentStatus = []

  for (let i = 0; i < settled.length; i++) {
    const { status, value, reason } = settled[i]
    const agentName = agents[i].name

    if (status === 'rejected') {
      agentStatus.push({ name: agentName, ok: false, error: reason?.message ?? 'timeout' })
      continue
    }

    agentStatus.push({ name: agentName, ok: true })

    // Sum totals
    for (const [k, v] of Object.entries(value.totals ?? {})) {
      totals[k] = (totals[k] ?? 0) + (Number(v) || 0)
    }

    // Merge by_user: group by exec_email, accumulate weighted duration
    for (const u of value.by_user ?? []) {
      const key = u.exec_email
      if (!byUserMap[key]) {
        byUserMap[key] = { exec_email: key, total_calls: 0, errors: 0, total_bytes: 0, _weighted_duration: 0 }
      }
      const agg = byUserMap[key]
      const calls = Number(u.total_calls) || 0
      agg.total_calls += calls
      agg.errors += Number(u.errors) || 0
      agg.total_bytes += Number(u.total_bytes) || 0
      agg._weighted_duration += (Number(u.avg_duration_ms) || 0) * calls
    }

    // Collect errors tagged with agent name
    for (const e of value.recent_errors ?? []) {
      recentErrors.push({ ...e, agent: agentName })
    }
  }

  const byUser = Object.values(byUserMap)
    .map(({ _weighted_duration, total_calls, ...rest }) => ({
      ...rest,
      total_calls,
      avg_duration_ms: total_calls > 0 ? Math.round(_weighted_duration / total_calls) : 0,
    }))
    .sort((a, b) => b.total_calls - a.total_calls)

  recentErrors.sort((a, b) => b.ts - a.ts)

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({
    by_user: byUser,
    totals,
    recent_errors: recentErrors.slice(0, 20),
    agents: agentStatus,
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
  if (action === 'bq-stats') return handleBqStats(res, email)
  return res.status(404).json({ error: 'not found' })
}
