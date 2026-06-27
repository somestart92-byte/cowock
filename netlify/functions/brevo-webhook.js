// Netlify Function: POST /api/brevo-webhook
// Receives Brevo transactional email webhooks (opens, clicks, bounces).
// Configure in Brevo → Transactional → Settings → Webhooks:
//   URL: https://your-site.netlify.app/.netlify/functions/brevo-webhook
//   Events: opened, clicks, hardBounces, softBounces, unsubscribed
//
// Since this is serverless (no persistent DB), we log the event and
// the CRM fetches stats on demand via email-stats function instead.
// To persist: swap the console.log for a write to Netlify Blobs or Supabase.

export async function handler(event) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }

  let payload;
  try { payload = JSON.parse(event.body); } catch {
    return { statusCode: 400, body: 'Invalid JSON' };
  }

  // Brevo sends an array of events
  const events = Array.isArray(payload) ? payload : [payload];
  for (const ev of events) {
    console.log(`[Brevo webhook] event=${ev.event} email=${ev.email} messageId=${ev['message-id']} ts=${ev.ts_epoch}`);
  }

  return { statusCode: 200, body: JSON.stringify({ received: events.length }) };
}
