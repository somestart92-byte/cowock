// Netlify Function: GET /api/email-stats?contactId=123
// Proxies to Google Apps Script to fetch open/click status per contact.
// Required env var: GAS_WEB_APP_URL

export async function handler(event) {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers: cors, body: '' };

  const gasUrl = process.env.GAS_WEB_APP_URL;
  if (!gasUrl) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: 'GAS_WEB_APP_URL not set', setup: true }) };
  }

  const { contactId } = event.queryStringParameters || {};
  const url = gasUrl + '?action=stats' + (contactId ? '&c=' + encodeURIComponent(contactId) : '');

  try {
    const res = await fetch(url, { redirect: 'follow' });
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text, emails: [] }; }
    return { statusCode: 200, headers: cors, body: JSON.stringify(data) };
  } catch (err) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: err.message }) };
  }
}
