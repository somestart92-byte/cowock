// Netlify Function: GET /api/check-config
// Returns whether GAS_WEB_APP_URL is configured and optionally pings GAS.

export async function handler(event) {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  const gasUrl = process.env.GAS_WEB_APP_URL;
  if (!gasUrl) {
    return { statusCode: 200, headers: cors, body: JSON.stringify({ configured: false, error: 'GAS_WEB_APP_URL not set in Netlify env vars' }) };
  }

  try {
    const res = await fetch(gasUrl + '?action=ping', { redirect: 'follow', signal: AbortSignal.timeout(8000) });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
    return { statusCode: 200, headers: cors, body: JSON.stringify({ configured: true, gasOk: !!data.ok, gasUser: data.user, ts: data.ts }) };
  } catch (err) {
    return { statusCode: 200, headers: cors, body: JSON.stringify({ configured: true, gasOk: false, error: err.message }) };
  }
}
