// Kuulis load test (doc 18). Every scenario behaves like the apps: HTTP for actions, one WebSocket
// per signed-in app for realtime events, drivers sending their position every few seconds.
//
//   k6 run -e BASE_URL=https://kuulis-qa.top8.uk -e PASSWORD=... loadtest/k6/kuulis.js
//
// Accounts come from `python manage.py loadtest-seed` (lt-p00001@loadtest.example.com …).
// Options (env):
//   SCENARIOS   comma list of drivers,riders,browsers,admins (default: all)
//   SCALE       multiplies DRIVERS, RIDES and BROWSERS (default 1)
//   DRIVERS     drivers online (600)      RIDES     riders doing full trips back to back (150)
//   BROWSERS    riders opening the app and quoting (1500)
//   DURATION    how long everyone stays (30m)        RAMP   time to bring everyone in (5m)
//   LOCATION_S  seconds between driver positions (4) ARRIVE_S / TRIP_S  simulated trip legs
//   P_ACCOUNTS / D_ACCOUNTS  seeded riders / drivers (5000 / 600)
//   ADMIN_TOKENS JSON [{access_token, refresh_token}] signed in by the runner (2FA)
//   TOKENS_PATH JSON {email: refresh_token} signed in by the runner before the test: those users
//               open the app already signed in (a token refresh, as in real life) instead of
//               typing their password. Accounts missing from it sign in with the password.

import http from 'k6/http';
import exec from 'k6/execution';
import { WebSocket } from 'k6/experimental/websockets';
import { setTimeout, clearTimeout, setInterval, clearInterval } from 'k6/timers';
import { Counter, Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API = `${BASE_URL}/api/v1`;
const WS_URL = `${BASE_URL.replace(/^http/, 'ws')}/api/v1/ws`;
const PASSWORD = __ENV.PASSWORD;
const DOMAIN = 'loadtest.example.com';
const SCALE = parseFloat(__ENV.SCALE || '1');
const DRIVERS = Math.round(parseInt(__ENV.DRIVERS || '600', 10) * SCALE);
const RIDES = Math.round(parseInt(__ENV.RIDES || '150', 10) * SCALE);
const BROWSERS = Math.round(parseInt(__ENV.BROWSERS || '1500', 10) * SCALE);
const P_ACCOUNTS = parseInt(__ENV.P_ACCOUNTS || '5000', 10);
const D_ACCOUNTS = parseInt(__ENV.D_ACCOUNTS || '600', 10);
const DURATION_S = seconds(__ENV.DURATION || '30m');
const RAMP_S = seconds(__ENV.RAMP || '5m');
const LOCATION_S = parseFloat(__ENV.LOCATION_S || '4');
const ARRIVE_S = parseFloat(__ENV.ARRIVE_S || '20');
const TRIP_S = parseFloat(__ENV.TRIP_S || '60');
const ADMIN_TOKENS = JSON.parse(__ENV.ADMIN_TOKENS || '[]');
// API server clock minus this machine's (measured by the runner) for cross-machine times.
const CLOCK_OFFSET_MS = parseInt(__ENV.CLOCK_OFFSET_MS || '0', 10);
const SCENARIOS = (__ENV.SCENARIOS || 'drivers,riders,browsers,admins').split(',');
const TOKEN_REFRESH_MS = 12 * 60 * 1000; // access tokens live 15 min
// Ride flows run back to back: never more riders than accounts left after the browsers.
const RIDER_POOL = P_ACCOUNTS - BROWSERS;

// One array per kind, indexed by account number - 1 (SharedArray: one copy for all VUs).
function loadTokens(kind, count) {
  if (!__ENV.TOKENS_PATH) return [];
  const tokens = JSON.parse(open(__ENV.TOKENS_PATH));
  const list = [];
  for (let n = 1; n <= count; n += 1) list.push(tokens[`lt-${kind}${String(n).padStart(5, '0')}@${DOMAIN}`] || '');
  return list;
}
const P_TOKENS = new SharedArray('p_tokens', () => loadTokens('p', P_ACCOUNTS));
const D_TOKENS = new SharedArray('d_tokens', () => loadTokens('d', D_ACCOUNTS));

function savedRefresh(email) {
  const m = email.match(/^lt-([pd])(\d+)@/);
  if (!m) return null;
  const list = m[1] === 'p' ? P_TOKENS : D_TOKENS;
  return list[parseInt(m[2], 10) - 1] || null;
}

if (!PASSWORD) throw new Error('PASSWORD is required');
if (DRIVERS > D_ACCOUNTS) throw new Error(`DRIVERS ${DRIVERS} > seeded drivers ${D_ACCOUNTS}`);
if (SCENARIOS.includes('riders') && RIDER_POOL < RIDES) {
  throw new Error(`Need ${BROWSERS + RIDES} rider accounts, seeded ${P_ACCOUNTS}`);
}

// --- Metrics ------------------------------------------------------------------------------------
const http5xx = new Counter('http_5xx');
const httpUnexpected = new Counter('http_unexpected');
const wsUnexpectedClose = new Counter('ws_unexpected_close');
const wsReconnects = new Counter('ws_reconnects');
const wsConnectMs = new Trend('ws_connect_ms', true);
const offerDeliveryMs = new Trend('offer_delivery_ms', true); // offer created -> driver socket
const rideAssignedMs = new Trend('ride_assigned_ms', true); // request -> driver_assigned event
const rideOk = new Rate('ride_completed');
const ridesNoDriver = new Counter('rides_no_driver');
const locationsSent = new Counter('driver_locations_sent');
const notJson = new Counter('http_not_json'); // proxy pages (HTML) where the API should answer
const locationsForwarded = new Counter('driver_locations_forwarded');

// --- Options ------------------------------------------------------------------------------------
const maxDuration = `${DURATION_S + RAMP_S + 300}s`;
const scenarios = {};
if (SCENARIOS.includes('drivers') && DRIVERS > 0) {
  scenarios.drivers = {
    executor: 'per-vu-iterations', exec: 'driver', vus: DRIVERS, iterations: 1, maxDuration,
  };
}
if (SCENARIOS.includes('riders') && RIDES > 0) {
  scenarios.riders = {
    executor: 'per-vu-iterations', exec: 'rider', vus: RIDES, iterations: 1, maxDuration,
  };
}
if (SCENARIOS.includes('browsers') && BROWSERS > 0) {
  scenarios.browsers = {
    executor: 'per-vu-iterations', exec: 'browser', vus: BROWSERS, iterations: 1, maxDuration,
  };
}
if (SCENARIOS.includes('admins') && ADMIN_TOKENS.length > 0) {
  scenarios.admins = {
    executor: 'per-vu-iterations', exec: 'admin', vus: ADMIN_TOKENS.length, iterations: 1,
    maxDuration,
  };
}

export const options = {
  scenarios,
  thresholds: {
    'http_req_duration{expected_response:true}': ['p(95)<300'],
    http_5xx: ['count==0'],
    offer_delivery_ms: ['p(95)<2000'],
    ride_assigned_ms: ['p(95)<5000'],
    ride_completed: ['rate>0.95'],
    http_not_json: ['count==0'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max', 'count'],
  discardResponseBodies: false,
  insecureSkipTLSVerify: false,
};

// --- Helpers ------------------------------------------------------------------------------------
function seconds(value) {
  const m = String(value).match(/^(\d+(?:\.\d+)?)(s|m|h)?$/);
  if (!m) throw new Error(`Bad duration ${value}`);
  return parseFloat(m[1]) * { s: 1, m: 60, h: 3600 }[m[2] || 's'];
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const jitter = (min, max) => min + Math.random() * (max - min);
const pad = (n) => String(n).padStart(5, '0');
const deadline = () => Date.now() + DURATION_S * 1000;

let area = null; // the Caracas service area from /config/public

function randomPoint() {
  const a = area || { min_lat: 10.45, max_lat: 10.52, min_lng: -66.95, max_lng: -66.8 };
  // Keep a margin from the edges so random walks stay inside.
  const lat = a.min_lat + (a.max_lat - a.min_lat) * jitter(0.15, 0.85);
  const lng = a.min_lng + (a.max_lng - a.min_lng) * jitter(0.15, 0.85);
  return { lat, lng };
}

let logged = 0;
function track(res, name, expected) {
  const bad = res.status >= 500 || res.status === 0;
  if (bad) http5xx.add(1, { name });
  else if (expected && !expected.includes(res.status)) httpUnexpected.add(1, { name, status: String(res.status) });
  if ((bad || (expected && !expected.includes(res.status))) && logged < 20) {
    logged += 1; // a few samples per VU are enough to see what is failing
    console.warn(`${name} -> ${res.status} ${String(res.body || res.error).slice(0, 200)}`);
  }
  return res;
}

// While the API restarts, the proxy in front of it can answer with an HTML page, even with a 200.
// `res.json()` throws on that and the throw ends the VU, so read bodies through here instead.
function json(res, path) {
  try {
    return path === undefined ? res.json() : res.json(path);
  } catch (e) {
    notJson.add(1, { status: String(res.status) });
    return null;
  }
}

class Session {
  constructor(email) {
    this.email = email;
    this.access = null;
    this.refresh = savedRefresh(email); // signed in before the test: the first fresh() refreshes
    this.at = 0;
  }

  headers() {
    return { Authorization: `Bearer ${this.access}`, 'Content-Type': 'application/json',
      'X-App-Platform': 'android', 'X-Client-Platform': 'loadtest' };
  }

  async login() {
    // Logins share one source IP here: on 429 wait what the API asks, like the app would.
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const res = track(
        await http.asyncRequest('POST', `${API}/auth/login`,
          JSON.stringify({ email: this.email, password: PASSWORD }),
          { headers: { 'Content-Type': 'application/json' }, tags: { name: 'auth_login' } }),
        'auth_login', [200, 429]);
      const body = res.status === 200 ? json(res) : null;
      if (body && body.access_token) {
        this.access = body.access_token;
        this.refresh = body.refresh_token;
        this.at = Date.now();
        return true;
      }
      if (res.status !== 429) return false;
      const wait = (json(res, 'error.details.retry_after') || 60) * 1000;
      await sleep(wait + jitter(0, 10000));
    }
    return false;
  }

  static fromTokens(tokens) {
    const s = new Session('admin');
    s.access = tokens.access_token;
    s.refresh = tokens.refresh_token;
    s.at = Date.now();
    return s;
  }

  async fresh() {
    if (this.access && Date.now() - this.at < TOKEN_REFRESH_MS) return true;
    if (this.refresh) {
      const res = track(
        await http.asyncRequest('POST', `${API}/auth/refresh`,
          JSON.stringify({ refresh_token: this.refresh }),
          { headers: { 'Content-Type': 'application/json' }, tags: { name: 'auth_refresh' } }),
        'auth_refresh', [200]);
      const body = res.status === 200 ? json(res) : null;
      if (body && body.access_token) {
        this.access = body.access_token;
        this.refresh = body.refresh_token;
        this.at = Date.now();
        return true;
      }
    }
    return this.email !== 'admin' && this.login();
  }

  async call(method, path, body, name, expected = [200, 201, 204]) {
    await this.fresh();
    const res = await http.asyncRequest(method, `${API}${path}`,
      body === undefined ? null : JSON.stringify(body),
      { headers: this.headers(), tags: { name } });
    return track(res, name, expected);
  }
}

// One realtime socket. `on(event, fn)` handlers; `waitFor(event, test, ms)` resolves with the
// matching data or null on timeout. With `reconnect`, an unexpected close reopens the socket with
// the same backoff as the app (1 s doubling up to 30 s), keeping the handlers.
class Realtime {
  constructor(session, reconnect = false) {
    this.session = session;
    this.reconnect = reconnect;
    this.attempts = 0;
    this.opened = 0;
    this.handlers = {};
    this.waiters = [];
    this.closing = false;
    this.ready = null;
  }

  get isOpen() {
    return Boolean(this.ws) && this.ws.readyState === 1;
  }

  retry() {
    const delay = Math.min(30000, 1000 * 2 ** this.attempts);
    this.attempts += 1;
    setTimeout(() => {
      if (this.closing) return;
      wsReconnects.add(1);
      this.session.fresh().catch(() => false).then(() => this.open());
    }, delay);
  }

  open() {
    const started = Date.now();
    this.ready = new Promise((resolve) => {
      const ws = new WebSocket(WS_URL);
      this.ws = ws;
      const timer = setTimeout(() => {
        resolve(false);
        if (this.reconnect && !this.closing) {
          try { ws.close(); } catch (e) { /* already closed */ }
        }
      }, 15000);
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: this.session.access }));
      ws.onmessage = (msg) => {
        let parsed;
        try { parsed = JSON.parse(msg.data); } catch (e) { return; }
        const { event, data } = parsed;
        if (event === 'ready') {
          clearTimeout(timer);
          this.attempts = 0;
          wsConnectMs.add(Date.now() - started);
          resolve(true);
        } else if (event === 'auth.expiring') {
          this.session.fresh().catch(() => false)
            .then(() => this.send({ type: 'auth', token: this.session.access }));
        }
        this.emit(event, data);
        if (event === 'ready' && this.opened++ > 0) this.emit('reconnected', null);
      };
      ws.onclose = (e) => {
        clearTimeout(timer);
        if (!this.closing) wsUnexpectedClose.add(1, { code: String(e && e.code) });
        resolve(false);
        if (this.reconnect && !this.closing) {
          this.retry();
          return;
        }
        this.waiters.forEach((w) => { clearTimeout(w.timer); w.resolve(null); });
        this.waiters = [];
      };
      ws.onerror = () => {};
    });
    return this.ready;
  }

  emit(event, data) {
    (this.handlers[event] || []).forEach((fn) => fn(data));
    this.waiters = this.waiters.filter((w) => {
      if (w.event !== event || !w.test(data)) return true;
      clearTimeout(w.timer);
      w.resolve(data);
      return false;
    });
  }

  on(event, fn) {
    (this.handlers[event] = this.handlers[event] || []).push(fn);
  }

  waitFor(event, test, ms) {
    return new Promise((resolve) => {
      const waiter = { event, test, resolve };
      waiter.timer = setTimeout(() => {
        this.waiters = this.waiters.filter((w) => w !== waiter);
        resolve(null);
      }, ms);
      this.waiters.push(waiter);
    });
  }

  send(obj) {
    try { this.ws.send(JSON.stringify(obj)); } catch (e) { /* closed */ }
  }

  close() {
    this.closing = true;
    try { this.ws.close(); } catch (e) { /* already closed */ }
  }
}

async function loadArea(session) {
  if (area) return;
  const res = await session.call('GET', '/config/public', undefined, 'config_public');
  if (res.status === 200) {
    const areas = json(res, 'service_areas') || [];
    area = areas.find((a) => a.name.toLowerCase() === 'caracas') || areas[0] || null;
  }
}

// Riders and drivers do not all arrive in the same second.
async function rampIn(index, total) {
  await sleep((RAMP_S * 1000 * index) / Math.max(total, 1) + jitter(0, 1000));
}

// --- Drivers ------------------------------------------------------------------------------------
let offerTimeoutS = 15;

export async function driver() {
  const index = exec.scenario.iterationInTest;
  const session = new Session(`lt-d${pad(index + 1)}@${DOMAIN}`);
  await rampIn(index, DRIVERS);
  const end = deadline();
  if (!(await session.fresh())) return;
  await loadArea(session);
  const cfg = await session.call('GET', '/config/public', undefined, 'config_public');
  if (cfg.status === 200) offerTimeoutS = json(cfg, 'offer_timeout_seconds') || offerTimeoutS;

  let pos = randomPoint();
  const online = await session.call('POST', '/drivers/me/online', pos, 'driver_online');
  if (online.status !== 200) return;
  await session.call('GET', '/drivers/me/state', undefined, 'driver_state');

  // Like the app, a driver's socket reconnects on its own; locations only count while it is open.
  const rt = new Realtime(session, true);
  await rt.open();
  let busy = false;

  const tick = setInterval(() => {
    pos = { lat: pos.lat + jitter(-0.0004, 0.0004), lng: pos.lng + jitter(-0.0004, 0.0004) };
    if (!rt.isOpen) return;
    rt.send({ type: 'location', lat: pos.lat, lng: pos.lng, heading: jitter(0, 359), speed: jitter(0, 12) });
    locationsSent.add(1);
  }, LOCATION_S * 1000);

  rt.on('ride.offer', (offer) => {
    if (busy) return;
    const sentAt = Date.parse(offer.expires_at) - offerTimeoutS * 1000;
    offerDeliveryMs.add(Math.max(0, Date.now() + CLOCK_OFFSET_MS - sentAt));
    busy = true;
    driveRide(session, rt, offer)
      .catch((e) => console.warn(`driveRide: ${e}`))
      .finally(() => { busy = false; });
  });

  // Keep serving after the deadline so the trips riders already requested can finish.
  const grace = (ARRIVE_S + TRIP_S) * 1500 + 60000;
  while (Date.now() < end + grace) await sleep(5000);
  while (busy && Date.now() < end + 2 * grace) await sleep(2000);
  clearInterval(tick);
  rt.close();
  await session.call('POST', '/drivers/me/offline', undefined, 'driver_offline', [200, 409]);
}

async function driveRide(session, rt, offer) {
  await sleep(jitter(800, 2500)); // reading the offer
  const id = offer.ride_id;
  const accepted = await session.call('POST', `/rides/${id}/accept`, undefined, 'ride_accept',
    [200, 409, 410]);
  if (accepted.status !== 200) return;
  await sleep(ARRIVE_S * 1000 * jitter(0.8, 1.2));
  if ((await session.call('POST', `/rides/${id}/arrive`, undefined, 'ride_arrive', [200, 409])).status !== 200) return;
  await session.call('POST', `/rides/${id}/messages`, { text: 'Ya llegué, estoy afuera' }, 'chat_send');
  await sleep(jitter(5000, 10000));
  if ((await session.call('POST', `/rides/${id}/start`, undefined, 'ride_start', [200, 409])).status !== 200) return;
  await sleep(TRIP_S * 1000 * jitter(0.8, 1.2));
  if ((await session.call('POST', `/rides/${id}/complete`, undefined, 'ride_complete', [200, 409])).status !== 200) return;
  await sleep(jitter(2000, 5000));
  await session.call('POST', `/rides/${id}/rating`, { stars: 5, tags: [] }, 'ride_rate');
}

// --- Riders doing full trips --------------------------------------------------------------------
export async function rider() {
  const index = exec.scenario.iterationInTest;
  await rampIn(index, RIDES);
  const end = deadline();
  // Each VU cycles through its own accounts (never shared with browsers or other VUs).
  const accounts = [];
  for (let n = BROWSERS + index; n < P_ACCOUNTS; n += RIDES) accounts.push(n + 1);
  let turn = 0;
  const sessions = {};

  while (Date.now() < end) {
    const n = accounts[turn % accounts.length];
    turn += 1;
    const session = sessions[n] || (sessions[n] = new Session(`lt-p${pad(n)}@${DOMAIN}`));
    if (!(await session.fresh())) { await sleep(5000); continue; }
    await loadArea(session);
    const ok = await rideOnce(session);
    rideOk.add(ok);
    await sleep(jitter(5000, 15000));
  }
}

async function rideOnce(session) {
  await session.call('GET', '/rides/active', undefined, 'ride_active');
  const unrated = await session.call('GET', '/rides/pending-rating', undefined, 'ride_pending_rating');
  const unratedId = unrated.status === 200 ? json(unrated, 'id') : null;
  if (unratedId) {
    await session.call('POST', `/rides/${unratedId}/rating`, { stars: 5, tags: [] }, 'ride_rate');
  }
  const pickup = randomPoint();
  const dropoff = randomPoint();
  const quote = await session.call('POST', '/rides/quote', {
    pickup: Object.assign({ address: 'Carga origen' }, pickup),
    dropoff: Object.assign({ address: 'Carga destino' }, dropoff),
    vehicle_type: 'moto',
  }, 'ride_quote');
  const quoteId = quote.status === 200 ? json(quote, 'quote_id') : null;
  if (!quoteId) return false;
  await sleep(jitter(2000, 5000)); // looking at the price

  const rt = new Realtime(session, true);
  if (!(await rt.open())) { rt.close(); return false; }
  const counter = { forwarded: 0 };
  rt.on('ride.driver_location', () => { counter.forwarded += 1; });
  // No try/finally: k6's JS engine (sobek) panics on finally blocks around await.
  const ok = await followRide(session, rt, quoteId);
  locationsForwarded.add(counter.forwarded);
  rt.close();
  return ok;
}

async function followRide(session, rt, quoteId) {
  const requestedAt = Date.now();
  const created = await session.call('POST', '/rides',
    { quote_id: quoteId, payment_method: 'cash_usd' }, 'ride_create', [201]);
  const id = created.status === 201 ? json(created, 'id') : null;
  if (!id) return false;
  const isRide = (d) => d && d.id === id;
  // Like the app: after a reconnect, re-read the ride in case an update was missed.
  rt.on('reconnected', () => {
    session.call('GET', `/rides/${id}`, undefined, 'ride_get').then((res) => {
      const ride = res.status === 200 ? json(res) : null;
      if (ride) rt.emit('ride.updated', ride);
    }).catch((e) => console.warn(`ride_get after reconnect: ${e}`));
  });

  const assigned = await rt.waitFor('ride.updated', (d) => isRide(d) && d.status !== 'searching', 200000);
  if (!assigned || assigned.status !== 'driver_assigned') {
    if (assigned && assigned.status === 'no_drivers') ridesNoDriver.add(1);
    else await session.call('POST', `/rides/${id}/cancel`, {}, 'ride_cancel', [200, 409]);
    return false;
  }
  rideAssignedMs.add(Date.now() - requestedAt);
  await session.call('GET', `/rides/${id}`, undefined, 'ride_get');
  await session.call('POST', `/rides/${id}/messages`, { text: 'Hola, voy saliendo' }, 'chat_send');

  const finished = ['completed', 'cancelled_by_driver', 'cancelled_by_admin'];
  const done = await rt.waitFor('ride.updated', (d) => isRide(d) && finished.includes(d.status),
    (ARRIVE_S + TRIP_S) * 1500 + 60000);
  await session.call('GET', `/rides/${id}/messages`, undefined, 'chat_list');
  if (!done || done.status !== 'completed') return false;
  await session.call('POST', `/rides/${id}/rating`, { stars: 5, tags: [] }, 'ride_rate');
  return true;
}

// --- Riders opening the app and quoting ---------------------------------------------------------
export async function browser() {
  const index = exec.scenario.iterationInTest;
  await rampIn(index, BROWSERS);
  const end = deadline();
  const session = new Session(`lt-p${pad(index + 1)}@${DOMAIN}`);
  if (!(await session.fresh())) return;
  await loadArea(session);

  while (Date.now() < end) {
    // App opens: same calls as the home screen, with the socket open while in the foreground.
    const rt = new Realtime(session);
    const opened = rt.open();
    await session.call('GET', '/config/public', undefined, 'config_public');
    await session.call('GET', '/users/me', undefined, 'users_me');
    await session.call('GET', '/rides/active', undefined, 'ride_active');
    await session.call('GET', '/rides/pending-rating', undefined, 'ride_pending_rating');
    await session.call('GET', '/rates', undefined, 'rates');
    await session.call('GET', '/notifications/unread-count', undefined, 'notifications_unread');
    await opened;
    const quotes = Math.random() < 0.6 ? 1 + Math.floor(Math.random() * 2) : 0;
    for (let q = 0; q < quotes; q += 1) {
      await sleep(jitter(3000, 8000));
      await session.call('POST', '/rides/quote', {
        pickup: Object.assign({ address: 'Carga origen' }, randomPoint()),
        dropoff: Object.assign({ address: 'Carga destino' }, randomPoint()),
        vehicle_type: 'moto',
      }, 'ride_quote');
    }
    if (Math.random() < 0.3) await session.call('GET', '/rides?limit=20', undefined, 'ride_history');
    if (Math.random() < 0.2) await session.call('GET', '/notifications?limit=20', undefined, 'notifications_list');
    await sleep(jitter(5000, 15000));
    rt.close();
    await sleep(jitter(20000, 60000)); // app in the background
  }
}

// --- Admin panel --------------------------------------------------------------------------------
export async function admin() {
  const index = exec.scenario.iterationInTest;
  const session = Session.fromTokens(ADMIN_TOKENS[index]);
  const end = deadline();
  let loops = 0;
  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const yearAgo = new Date(Date.now() - 180 * 86400000).toISOString().slice(0, 10);
  await sleep(jitter(0, 10000));
  while (Date.now() < end) {
    await session.call('GET', '/admin/rides/live', undefined, 'admin_live');
    await session.call('GET', '/admin/drivers/online', undefined, 'admin_online_drivers');
    await session.call('GET', '/admin/overview', undefined, 'admin_overview');
    if (loops % 6 === 0) {
      await session.call('GET', `/admin/metrics?from=${monthAgo}&to=${today}`, undefined, 'admin_metrics_30d');
      await session.call('GET', '/admin/rides?limit=50', undefined, 'admin_rides');
      await session.call('GET', `/admin/finance/summary?from=${monthAgo}&to=${today}`, undefined, 'admin_finance');
    }
    if (loops % 30 === 0) {
      await session.call('GET', `/admin/metrics?from=${yearAgo}&to=${today}`, undefined, 'admin_metrics_180d');
    }
    loops += 1;
    await sleep(10000);
  }
}

export function handleSummary(data) {
  return {
    stdout: JSON.stringify({ thresholds_ok: Object.values(data.metrics).every((m) => !m.thresholds || Object.values(m.thresholds).every((t) => t.ok)) }) + '\n',
    [__ENV.SUMMARY_PATH || 'summary.json']: JSON.stringify(data, null, 1),
  };
}
