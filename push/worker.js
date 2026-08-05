// Discover Crypto - instant upload notifier (Cloudflare Worker).
//
// YouTube's WebSub (PubSubHubbub) hub POSTs here the moment a video publishes.
// This Worker verifies the subscription, receives the push, writes an AI comment
// in the partner's voice, and sends it to Telegram in seconds. A cron trigger
// re-subscribes so the subscription never lapses.
//
// Bindings / vars set in Cloudflare (see push/README-push.md):
//   SEEN                KV namespace (dedup)
//   ANTHROPIC_API_KEY   secret (optional; falls back if unset)
//   TELEGRAM_BOT_TOKEN  secret
//   TELEGRAM_CHAT_ID    text
//   CHANNEL_ID          text  (UCjemQfjaXAzA-95RKoy9n_g)
//   WORKER_URL          text  (https://<name>.<subdomain>.workers.dev)
//   PATH_TOKEN          text  (the random token in the callback path)
//   SKOOL_LINK          text
//   COMMENT_FALLBACK, COMMENT_FALLBACK_SHORTS  text

const SHORTS_CTA = "Tap our channel and hit the top link.";

const SYSTEM_PROMPT =
  "You write ONE pinned comment for a new Discover Crypto YouTube upload, " +
  "tailored to the video's topic. Voice: short, one line, value and education " +
  "first, calm and confident. Never hype, never salesy.\n\n" +
  "Match the style of these real examples exactly:\n" +
  "- Learn how to short so you can make money regardless of the market direction\n" +
  "- Learn to build wealth with crypto\n" +
  "- Follow our wealth building strategies\n" +
  "- We teach these strategies here\n\n" +
  "Rules:\n" +
  "- One short sentence, clearly tied to the video title's topic.\n" +
  "- Frame it as what the viewer will learn or what the community teaches.\n" +
  "- No hashtags, no emojis, no quotation marks.\n" +
  "- Never use the word 'free'.\n" +
  "- Never use em dashes; use plain hyphens or rephrase.\n" +
  "- Do NOT include any link or URL.\n" +
  "- Output only the sentence, with no preamble or explanation.";

function decodeXml(s) {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&amp;/g, "&");
}

function parseEntry(xml) {
  if (xml.includes("deleted-entry")) return null; // ignore deletions
  const entry = (xml.match(/<entry>[\s\S]*?<\/entry>/) || [])[0];
  if (!entry) return null;
  const idm = entry.match(/<yt:videoId>([^<]+)<\/yt:videoId>/);
  if (!idm) return null;
  const tm = entry.match(/<title>([\s\S]*?)<\/title>/);
  return { vid: idm[1], title: tm ? decodeXml(tm[1].trim()) : "(untitled)" };
}

async function isShort(vid) {
  try {
    const r = await fetch(`https://www.youtube.com/shorts/${vid}`, {
      method: "GET",
      redirect: "manual",
      headers: { "User-Agent": "Mozilla/5.0" },
    });
    return r.status === 200;
  } catch {
    return false;
  }
}

async function generateComment(title, short, env) {
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-opus-5",
      max_tokens: 1024,
      output_config: { effort: "low" },
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: `Video title: ${title}` }],
    }),
  });
  if (!r.ok) throw new Error(`anthropic ${r.status}`);
  const data = await r.json();
  let text = (data.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("")
    .trim()
    .replace(/^["']+|["']+$/g, "")
    .trim();
  if (!text) throw new Error("empty generation");
  if (short) {
    if (!/[.!?]$/.test(text)) text += ".";
    return `${text} ${SHORTS_CTA}`;
  }
  return `${text.replace(/\.+$/, "")} - ${env.SKOOL_LINK}`;
}

function buildComment(title, short, env) {
  if (env.ANTHROPIC_API_KEY) {
    return generateComment(title, short, env)
      .then((c) => [c, "AI"])
      .catch((e) => {
        console.log(`AI failed for '${title}': ${e}`);
        return [short ? env.COMMENT_FALLBACK_SHORTS : env.COMMENT_FALLBACK, "fallback"];
      });
  }
  return Promise.resolve([short ? env.COMMENT_FALLBACK_SHORTS : env.COMMENT_FALLBACK, "fallback"]);
}

async function sendTelegram(env, text) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_CHAT_ID,
      text,
      disable_web_page_preview: true,
    }),
  });
  if (!r.ok) throw new Error(`telegram ${r.status}`);
}

async function handleNotification(xml, env) {
  const entry = parseEntry(xml);
  if (!entry) return;
  const key = `seen:${entry.vid}`;
  if (await env.SEEN.get(key)) return; // dedup (covers duplicate pings + title edits)
  await env.SEEN.put(key, "1", { expirationTtl: 60 * 60 * 24 * 90 }); // 90 days

  const short = await isShort(entry.vid);
  const kind = short ? "Short" : "video";
  const [comment, source] = await buildComment(entry.title, short, env);

  await sendTelegram(
    env,
    `New Discover Crypto ${kind}  (${source} comment)\n\n` +
      `${entry.title}\n` +
      `https://youtu.be/${entry.vid}\n\n` +
      "Tap to open its comments page (post + pin here):\n" +
      `https://studio.youtube.com/video/${entry.vid}/comments\n\n` +
      "The exact comment to pin is in the next message - tap it to copy."
  );
  await sendTelegram(env, comment);
}

async function subscribe(env) {
  const topic = `https://www.youtube.com/xml/feeds/videos.xml?channel_id=${env.CHANNEL_ID}`;
  const callback = `${env.WORKER_URL}/yt/${env.PATH_TOKEN}`;
  const body = new URLSearchParams({
    "hub.mode": "subscribe",
    "hub.topic": topic,
    "hub.callback": callback,
    "hub.verify": "async",
    "hub.lease_seconds": "864000",
  });
  const r = await fetch("https://pubsubhubbub.appspot.com/subscribe", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });
  return r.status;
}

async function seedCurrent(env) {
  // Mark the current uploads as already-seen so a first subscribe never
  // backfill-spams. Uses the real feed path (not /xml/feeds/).
  try {
    const r = await fetch(
      `https://www.youtube.com/feeds/videos.xml?channel_id=${env.CHANNEL_ID}`,
      { headers: { "User-Agent": "Mozilla/5.0" } }
    );
    const xml = await r.text();
    const ids = [...xml.matchAll(/<yt:videoId>([^<]+)<\/yt:videoId>/g)].map((m) => m[1]);
    await Promise.all(
      ids.map((id) => env.SEEN.put(`seen:${id}`, "1", { expirationTtl: 60 * 60 * 24 * 90 }))
    );
    return ids.length;
  } catch (e) {
    console.log(`seed failed: ${e}`);
    return 0;
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const expected = `/yt/${env.PATH_TOKEN}`;

    if (url.pathname !== expected) {
      return new Response("not found", { status: 404 });
    }

    // Manual one-time kickoff: seed current uploads, then subscribe.
    if (url.searchParams.get("action") === "subscribe") {
      const seeded = await seedCurrent(env);
      const status = await subscribe(env);
      return new Response(`seeded ${seeded} existing uploads; subscribe returned ${status}`, {
        status: 200,
      });
    }

    // WebSub verification handshake (GET with hub.challenge).
    if (request.method === "GET") {
      const challenge = url.searchParams.get("hub.challenge");
      if (challenge) return new Response(challenge, { status: 200 });
      return new Response("ok", { status: 200 });
    }

    // WebSub push (POST with the Atom entry). Respond fast, process in the background.
    if (request.method === "POST") {
      const xml = await request.text();
      ctx.waitUntil(handleNotification(xml, env));
      return new Response("", { status: 204 });
    }

    return new Response("method not allowed", { status: 405 });
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(subscribe(env)); // renew the lease so the subscription never lapses
  },
};
