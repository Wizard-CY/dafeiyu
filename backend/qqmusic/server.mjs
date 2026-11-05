import http from 'node:http';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  login_qr_create,
  login_qr_check,
  login_status,
  login_refresh,
  search,
  song_url,
} from './vendor/qqmusic-api-enhanced/main.js';

const PORT = Number(process.env.QQMUSIC_PORT || 3311);
const COOKIE_FILE = fileURLToPath(new URL('./cookie.json', import.meta.url));
const LATEST = { qrsig: '', ptqrtoken: '', at: 0 };
const SESSIONS = new Map();
let POLLING = false;

function readCookie() {
  try {
    return JSON.parse(readFileSync(COOKIE_FILE, 'utf8'));
  } catch {
    return null;
  }
}

function writeCookie(value) {
  writeFileSync(COOKIE_FILE, JSON.stringify(value, null, 2), 'utf8');
}

function json(res, code, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(body);
}

function stripTags(text) {
  return String(text || '').replace(/<[^>]+>/g, '');
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  try {
    if (url.pathname === '/health') {
      const saved = readCookie();
      return json(res, 200, { ok: true, logged: Boolean(saved && saved.cookieStr), uin: saved?.uin || '' });
    }
    if (url.pathname === '/login/qr') {
      const qrType = url.searchParams.get('type') || 'qq';
      const qr = await login_qr_create({ type: qrType });
      if (qrType === 'mobile') {
        const qrcodeID = qr.body?.qrcodeID || '';
        LATEST.qrsig = qrcodeID;
        LATEST.ptqrtoken = '';
        LATEST.at = Date.now();
        if (qrcodeID) {
          SESSIONS.set(qrcodeID, { type: 'mobile', at: Date.now() });
          while (SESSIONS.size > 8) SESSIONS.delete(SESSIONS.keys().next().value);
        }
        return json(res, 200, { code: qr.body?.code, type: 'mobile', qrcode: qr.body?.qrcode || '', qrcodeID, qrsig: qrcodeID });
      }
      LATEST.qrsig = qr.body?.qrsig || '';
      LATEST.ptqrtoken = qr.body?.ptqrtoken || '';
      LATEST.at = Date.now();
      if (LATEST.qrsig) {
        SESSIONS.set(LATEST.qrsig, { ptqrtoken: LATEST.ptqrtoken, at: LATEST.at });
        while (SESSIONS.size > 8) {
          SESSIONS.delete(SESSIONS.keys().next().value);
        }
      }
      return json(res, 200, { code: qr.body?.code, qrsig: LATEST.qrsig, ptqrtoken: LATEST.ptqrtoken, qrimg: qr.body?.qrimg || '', url: qr.body?.url || '' });
    }
    if (url.pathname === '/login/check') {
      const qrsig = url.searchParams.get('qrsig') || LATEST.qrsig;
      const session = SESSIONS.get(qrsig);
      let check;
      if (session?.type === 'mobile') {
        check = await login_qr_check({ type: 'mobile', qrcodeID: qrsig });
      } else {
        const ptqrtoken = url.searchParams.get('ptqrtoken') || session?.ptqrtoken || (qrsig === LATEST.qrsig ? LATEST.ptqrtoken : '');
        if (!qrsig || !ptqrtoken) return json(res, 400, { error: 'missing qrsig or ptqrtoken' });
        check = await login_qr_check({ type: 'qq', qrsig, ptqrtoken });
      }
      const body = check.body || {};
      if (body.code === 200 && body.cookieStr) {
        writeCookie({ cookieStr: body.cookieStr, uin: body.uin || '', savedAt: Date.now() });
      }
      return json(res, 200, {
        code: body.code,
        message: body.message || '',
        uin: body.uin || '',
        cookieSaved: Boolean(body.code === 200 && body.cookieStr),
      });
    }
    if (url.pathname === '/login/sessions') {
      const rows = [...SESSIONS.entries()].map(([sig, s]) => ({ sig: sig.slice(0, 8), lastCode: s.lastCode || 0, age: Math.round((Date.now() - s.at) / 1000) }));
      return json(res, 200, { sessions: rows });
    }
    if (url.pathname === '/login/cookie' && req.method === 'POST') {
      let raw = '';
      for await (const chunk of req) raw += chunk;
      let body = {};
      try { body = JSON.parse(raw); } catch { body = {}; }
      const cookie = String(body.cookie || '').trim();
      if (!cookie) return json(res, 400, { ok: false, error: 'empty cookie' });
      const status = await login_status({ cookie });
      let uin = status.body?.uin || '';
      let accepted = Boolean(status.body?.isLogin);
      if (!accepted && /qm_keyst=/.test(cookie)) {
        try {
          const probe = await song_url({ id: '0039MnYb0qxYhV', type: '128', cookie });
          accepted = Boolean(probe.body?.data?.[0]?.url);
        } catch {
          accepted = false;
        }
      }
      if (accepted) {
        writeCookie({ cookieStr: status.body?.cookieStr || cookie, uin, savedAt: Date.now() });
        return json(res, 200, { ok: true, uin, nickname: status.body?.nickname || '' });
      }
      return json(res, 400, { ok: false, error: 'cookie not logged in' });
    }
    if (url.pathname === '/login/status') {
      const saved = readCookie();
      if (!saved?.cookieStr) return json(res, 200, { logged: false });
      const status = await login_status({ cookie: saved.cookieStr });
      return json(res, 200, { logged: true, uin: saved.uin, body: status.body });
    }
    if (url.pathname === '/login/refresh') {
      const saved = readCookie();
      if (!saved?.cookieStr) return json(res, 200, { ok: false, error: 'not logged in' });
      const refreshed = await login_refresh({ cookie: saved.cookieStr });
      const cookieStr = refreshed.body?.cookieStr || refreshed.body?.cookie || '';
      if (cookieStr) writeCookie({ cookieStr, uin: saved.uin, savedAt: Date.now() });
      return json(res, 200, { ok: Boolean(cookieStr) });
    }
    if (url.pathname === '/search') {
      const keyword = url.searchParams.get('key') || '';
      const limit = Math.min(Number(url.searchParams.get('limit') || 8), 20);
      const r = await search({ keywords: keyword, type: 0, limit });
      const items = r.body?.data?.body?.item_song || [];
      return json(res, 200, {
        songs: items.map((song) => ({
          mid: song.mid,
          name: song.name,
          title: stripTags(song.title),
          singers: (song.singer || []).map((s) => stripTags(s.name)).join(' / '),
          album: stripTags(song.album?.name || ''),
          interval: Number(song.interval || 0),
        })),
      });
    }
    if (url.pathname === '/song/url') {
      const mid = url.searchParams.get('mid') || '';
      const type = url.searchParams.get('type') || '320';
      const saved = readCookie();
      const r = await song_url({ id: mid, type, cookie: saved?.cookieStr || '' });
      const item = r.body?.data?.[0] || {};
      return json(res, 200, { url: item.url || '', code: r.body?.code, mid });
    }
    return json(res, 404, { error: 'not found' });
  } catch (err) {
    return json(res, 500, { error: String(err?.message || err) });
  }
});


async function pollSessions() {
  if (POLLING) return;
  POLLING = true;
  try {
    for (const [qrsig, session] of SESSIONS) {
      if (session.type !== 'mobile' && !session.ptqrtoken) continue;
      if (Date.now() - session.at > 10 * 60 * 1000) {
        SESSIONS.delete(qrsig);
        continue;
      }
      try {
        const check = session.type === 'mobile'
          ? await login_qr_check({ type: 'mobile', qrcodeID: qrsig })
          : await login_qr_check({ type: 'qq', qrsig, ptqrtoken: session.ptqrtoken });
        const body = check.body || {};
        if (body.code !== 801) {
          console.log('qr state', qrsig.slice(0, 8), body.code, body.message || '');
        }
        session.lastCode = body.code;
        if (body.code === 200 && body.cookieStr) {
          writeCookie({ cookieStr: body.cookieStr, uin: body.uin || '', savedAt: Date.now() });
          SESSIONS.delete(qrsig);
          console.log('qqmusic login saved', body.uin || '');
        } else if (body.code === 800) {
          SESSIONS.delete(qrsig);
        }
      } catch {
        // keep the session for the next tick
      }
    }
  } finally {
    POLLING = false;
  }
}

setInterval(pollSessions, 3000);


async function refreshCookie() {
  const saved = readCookie();
  if (!saved?.cookieStr) return;
  try {
    const refreshed = await login_refresh({ cookie: saved.cookieStr });
    const cookieStr = refreshed.body?.cookieStr || refreshed.body?.cookie || '';
    if (cookieStr && cookieStr !== saved.cookieStr) {
      writeCookie({ cookieStr, uin: saved.uin, savedAt: Date.now() });
      console.log('qqmusic cookie refreshed');
    }
  } catch {
    // refresh is best effort
  }
}

setInterval(refreshCookie, 6 * 3600 * 1000);

server.listen(PORT, '127.0.0.1', () => {
  console.log('qqmusic backend listening on', PORT);
});
