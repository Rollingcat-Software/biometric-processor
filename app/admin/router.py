"""Admin dashboard web routes.

Serves the admin dashboard HTML interface.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin-ui"])

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_template(template_name: str, **kwargs) -> str:
    """Render a simple HTML template.

    Args:
        template_name: Template file name.
        **kwargs: Template variables.

    Returns:
        Rendered HTML string.
    """
    template_path = TEMPLATE_DIR / template_name
    if template_path.exists():
        template = template_path.read_text()
        for key, value in kwargs.items():
            template = template.replace(f"{{{{ {key} }}}}", str(value))
        return template

    # Return inline template if file doesn't exist
    return get_inline_template(template_name, **kwargs)


def get_inline_template(template_name: str, **kwargs) -> str:
    """Get inline HTML template."""
    if template_name == "dashboard.html":
        return get_dashboard_template(**kwargs)
    elif template_name == "sessions.html":
        return get_sessions_template(**kwargs)
    elif template_name == "incidents.html":
        return get_incidents_template(**kwargs)
    else:
        return get_base_template(title="Admin", content="<p>Page not found</p>")


def get_base_template(title: str, content: str, active_page: str = "") -> str:
    """Get base HTML template with navigation."""
    nav_items = [
        ("dashboard", "/admin", "Dashboard"),
        ("sessions", "/admin/sessions", "Sessions"),
        ("incidents", "/admin/incidents", "Incidents"),
        ("metrics", "/admin/metrics", "Metrics"),
        ("config", "/admin/config", "Configuration"),
    ]

    nav_html = ""
    for key, url, label in nav_items:
        active_class = "active" if key == active_page else ""
        nav_html += f'<a href="{url}" class="nav-link {active_class}">{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Biometric Admin</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .header {{ background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ font-size: 1.5rem; }}
        .nav {{ display: flex; gap: 1rem; }}
        .nav-link {{ color: #a0a0a0; text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; }}
        .nav-link:hover, .nav-link.active {{ color: white; background: rgba(255,255,255,0.1); }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
        .card {{ background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 1.5rem; margin-bottom: 1.5rem; }}
        .card-title {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; color: #333; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }}
        .stat-card {{ text-align: center; padding: 2rem; }}
        .stat-value {{ font-size: 2.5rem; font-weight: 700; color: #1a1a2e; }}
        .stat-label {{ color: #666; margin-top: 0.5rem; }}
        .status-healthy {{ color: #22c55e; }}
        .status-warning {{ color: #f59e0b; }}
        .status-error {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f9f9f9; font-weight: 600; }}
        .badge {{ display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
        .badge-low {{ background: #dcfce7; color: #166534; }}
        .badge-medium {{ background: #fef3c7; color: #92400e; }}
        .badge-high {{ background: #fee2e2; color: #991b1b; }}
        .badge-critical {{ background: #991b1b; color: white; }}
        .btn {{ padding: 0.5rem 1rem; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; }}
        .btn-primary {{ background: #3b82f6; color: white; }}
        .btn-primary:hover {{ background: #2563eb; }}
        .btn-danger {{ background: #ef4444; color: white; }}
        .refresh-btn {{ background: none; border: 1px solid #ddd; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }}
    </style>
</head>
<body>
    <header class="header">
        <h1>Biometric Processor Admin</h1>
        <nav class="nav">{nav_html}</nav>
    </header>
    <main class="container">
        {content}
    </main>
    <script>
        async function fetchData(url) {{
            const response = await fetch(url);
            return response.json();
        }}

        function formatNumber(num) {{
            return new Intl.NumberFormat().format(num);
        }}

        function refreshDashboard() {{
            location.reload();
        }}
    </script>
</body>
</html>"""


def get_dashboard_template(**kwargs) -> str:
    """Get dashboard HTML template."""
    content = """
    <div class="grid">
        <div class="card stat-card">
            <div class="stat-value" id="enrollments">--</div>
            <div class="stat-label">Total Enrollments</div>
        </div>
        <div class="card stat-card">
            <div class="stat-value" id="verifications">--</div>
            <div class="stat-label">Verifications (24h)</div>
        </div>
        <div class="card stat-card">
            <div class="stat-value" id="active-sessions">--</div>
            <div class="stat-label">Active Sessions</div>
        </div>
        <div class="card stat-card">
            <div class="stat-value" id="incidents">--</div>
            <div class="stat-label">Incidents (24h)</div>
        </div>
    </div>

    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2 class="card-title">System Health</h2>
            <button class="refresh-btn" onclick="refreshHealth()">Refresh</button>
        </div>
        <div id="health-status">Loading...</div>
    </div>

    <div class="card">
        <h2 class="card-title">Recent Incidents</h2>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Session</th>
                    <th>Type</th>
                    <th>Severity</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody id="incidents-table">
                <tr><td colspan="5">Loading...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function loadDashboard() {
            try {
                const [metrics, health, incidents] = await Promise.all([
                    fetchData('/api/admin/metrics/dashboard'),
                    fetchData('/api/admin/health'),
                    fetchData('/api/admin/incidents?page_size=5')
                ]);

                document.getElementById('enrollments').textContent = formatNumber(metrics.enrollments.total);
                document.getElementById('verifications').textContent = formatNumber(metrics.verifications.total);
                document.getElementById('active-sessions').textContent = formatNumber(metrics.proctoring.active_sessions);
                document.getElementById('incidents').textContent = formatNumber(metrics.proctoring.total_incidents);

                const healthHtml = Object.entries(health.components).map(([name, data]) => {
                    const statusClass = data.status === 'healthy' ? 'status-healthy' : 'status-error';
                    return `<span class="${statusClass}">${name}: ${data.status}</span>`;
                }).join(' | ');
                document.getElementById('health-status').innerHTML = healthHtml;

                const incidentsHtml = incidents.incidents.map(inc => `
                    <tr>
                        <td>${new Date(inc.detected_at).toLocaleString()}</td>
                        <td>${inc.session_id}</td>
                        <td>${inc.type}</td>
                        <td><span class="badge badge-${inc.severity}">${inc.severity}</span></td>
                        <td>${inc.review_status}</td>
                    </tr>
                `).join('');
                document.getElementById('incidents-table').innerHTML = incidentsHtml;

            } catch (e) {
                console.error('Failed to load dashboard:', e);
            }
        }

        function refreshHealth() {
            loadDashboard();
        }

        loadDashboard();
        setInterval(loadDashboard, 30000);
    </script>
    """
    return get_base_template(title="Dashboard", content=content, active_page="dashboard")


def get_sessions_template(**kwargs) -> str:
    """Get sessions list HTML template."""
    content = """
    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h2 class="card-title" style="margin: 0;">Proctoring Sessions</h2>
            <div>
                <select id="status-filter" onchange="loadSessions()">
                    <option value="">All Status</option>
                    <option value="started">Started</option>
                    <option value="completed">Completed</option>
                    <option value="flagged">Flagged</option>
                </select>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Session ID</th>
                    <th>Exam</th>
                    <th>User</th>
                    <th>Status</th>
                    <th>Risk Score</th>
                    <th>Incidents</th>
                    <th>Started</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="sessions-table">
                <tr><td colspan="8">Loading...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function loadSessions() {
            const status = document.getElementById('status-filter').value;
            const url = '/api/admin/sessions' + (status ? `?status=${status}` : '');
            const data = await fetchData(url);

            const html = data.sessions.map(s => `
                <tr>
                    <td><a href="/admin/sessions/${s.id}">${s.id}</a></td>
                    <td>${s.exam_id}</td>
                    <td>${s.user_id}</td>
                    <td><span class="badge badge-${s.status === 'flagged' ? 'high' : 'low'}">${s.status}</span></td>
                    <td>${(s.risk_score * 100).toFixed(0)}%</td>
                    <td>${s.incident_count}</td>
                    <td>${new Date(s.started_at).toLocaleString()}</td>
                    <td>
                        ${s.status === 'started' ? '<button class="btn btn-danger" onclick="terminateSession(\\'' + s.id + '\\')">Terminate</button>' : '-'}
                    </td>
                </tr>
            `).join('');
            document.getElementById('sessions-table').innerHTML = html;
        }

        async function terminateSession(id) {
            if (!confirm('Are you sure you want to terminate this session?')) return;
            const reason = prompt('Enter termination reason:');
            if (!reason || reason.length < 10) {
                alert('Reason must be at least 10 characters');
                return;
            }
            await fetch(`/api/admin/sessions/${id}/terminate?reason=${encodeURIComponent(reason)}`, { method: 'POST' });
            loadSessions();
        }

        loadSessions();
    </script>
    """
    return get_base_template(title="Sessions", content=content, active_page="sessions")


def get_incidents_template(**kwargs) -> str:
    """Get incidents list HTML template."""
    content = """
    <div class="card">
        <h2 class="card-title">Incidents</h2>
        <div style="margin-bottom: 1rem; display: flex; gap: 1rem;">
            <select id="severity-filter" onchange="loadIncidents()">
                <option value="">All Severity</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
            </select>
            <select id="review-filter" onchange="loadIncidents()">
                <option value="">All Status</option>
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="dismissed">Dismissed</option>
            </select>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Session</th>
                    <th>Type</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="incidents-table">
                <tr><td colspan="6">Loading...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function loadIncidents() {
            const severity = document.getElementById('severity-filter').value;
            const review = document.getElementById('review-filter').value;
            let url = '/api/admin/incidents?page_size=50';
            if (severity) url += `&severity=${severity}`;
            if (review) url += `&review_status=${review}`;

            const data = await fetchData(url);

            const html = data.incidents.map(i => `
                <tr>
                    <td>${new Date(i.detected_at).toLocaleString()}</td>
                    <td><a href="/admin/sessions/${i.session_id}">${i.session_id}</a></td>
                    <td>${i.type}</td>
                    <td><span class="badge badge-${i.severity}">${i.severity}</span></td>
                    <td>${i.review_status}</td>
                    <td>
                        ${i.review_status === 'pending' ? `
                            <button class="btn btn-primary" onclick="reviewIncident('${i.id}', 'confirm')">Confirm</button>
                            <button class="btn" onclick="reviewIncident('${i.id}', 'dismiss')">Dismiss</button>
                        ` : '-'}
                    </td>
                </tr>
            `).join('');
            document.getElementById('incidents-table').innerHTML = html;
        }

        async function reviewIncident(id, action) {
            await fetch(`/api/admin/incidents/${id}/review?action=${action}`, { method: 'POST' });
            loadIncidents();
        }

        loadIncidents();
    </script>
    """
    return get_base_template(title="Incidents", content=content, active_page="incidents")


# ============================================================================
# Route Handlers
# ============================================================================


@admin_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render admin dashboard."""
    return HTMLResponse(content=get_dashboard_template())


@admin_router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request) -> HTMLResponse:
    """Render sessions list page."""
    return HTMLResponse(content=get_sessions_template())


@admin_router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str) -> HTMLResponse:
    """Render session detail page."""
    content = f"""
    <div class="card">
        <h2 class="card-title">Session: {session_id}</h2>
        <div id="session-details">Loading...</div>
    </div>
    <script>
        async function loadSession() {{
            const data = await fetchData('/api/admin/sessions/{session_id}');
            document.getElementById('session-details').innerHTML = `
                <p><strong>Exam:</strong> ${{data.exam_id}}</p>
                <p><strong>User:</strong> ${{data.user_id}}</p>
                <p><strong>Status:</strong> ${{data.status}}</p>
                <p><strong>Risk Score:</strong> ${{(data.risk_score * 100).toFixed(1)}}%</p>
                <p><strong>Duration:</strong> ${{data.duration_minutes}} minutes</p>
                <p><strong>Incidents:</strong> ${{data.incidents.length}}</p>
            `;
        }}
        loadSession();
    </script>
    """
    return HTMLResponse(content=get_base_template(title=f"Session {session_id}", content=content))


@admin_router.get("/incidents", response_class=HTMLResponse)
async def incidents_list(request: Request) -> HTMLResponse:
    """Render incidents list page."""
    return HTMLResponse(content=get_incidents_template())


@admin_router.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request) -> HTMLResponse:
    """Render metrics page."""
    content = """
    <div class="grid">
        <div class="card">
            <h2 class="card-title">Performance Metrics</h2>
            <div id="perf-metrics">Loading...</div>
        </div>
        <div class="card">
            <h2 class="card-title">Real-time Stats</h2>
            <div id="realtime-stats">Loading...</div>
        </div>
    </div>
    <script>
        async function loadMetrics() {
            const [dashboard, realtime] = await Promise.all([
                fetchData('/api/admin/metrics/dashboard'),
                fetchData('/api/admin/metrics/realtime')
            ]);

            document.getElementById('perf-metrics').innerHTML = `
                <p>Avg Response Time: ${dashboard.performance.avg_response_time_ms}ms</p>
                <p>P95 Response Time: ${dashboard.performance.p95_response_time_ms}ms</p>
                <p>Requests/sec: ${dashboard.performance.requests_per_second}</p>
            `;

            document.getElementById('realtime-stats').innerHTML = `
                <p>Active Connections: ${realtime.active_connections}</p>
                <p>Requests in Flight: ${realtime.requests_in_flight}</p>
                <p>Memory Usage: ${realtime.memory_usage_mb} MB</p>
                <p>CPU: ${realtime.cpu_percent}%</p>
            `;
        }
        loadMetrics();
        setInterval(loadMetrics, 5000);
    </script>
    """
    return HTMLResponse(content=get_base_template(title="Metrics", content=content, active_page="metrics"))


@admin_router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    """Render configuration page."""
    content = """
    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2 class="card-title">System Configuration</h2>
            <button class="btn btn-primary" onclick="reloadConfig()">Reload Config</button>
        </div>
        <pre id="config-json" style="background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow: auto;">Loading...</pre>
    </div>
    <script>
        async function loadConfig() {
            const config = await fetchData('/api/admin/config');
            document.getElementById('config-json').textContent = JSON.stringify(config, null, 2);
        }

        async function reloadConfig() {
            await fetch('/api/admin/config/reload', { method: 'POST' });
            alert('Configuration reloaded');
            loadConfig();
        }

        loadConfig();
    </script>
    """
    return HTMLResponse(content=get_base_template(title="Configuration", content=content, active_page="config"))
