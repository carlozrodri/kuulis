/**
 * Support and help center (doc 13), pure logic so it can be unit tested: help topics, conversation labels
 * (unread, "Te respondimos"), what a closed conversation still allows, the lost item states, the guided
 * flows offered from a ride and where a support notification opens. No React and no network.
 * Contract: docs/produccion/13-soporte-y-ayuda.md; the API decides again.
 */
import { isOpenReport } from './reports';
import type {
  AppConfig,
  HelpArticleSummary,
  HelpAudience,
  HelpTopic,
  LostItem,
  Report,
  ReportMessage,
  Ride,
} from './types';

// ── Limits (the API checks them again) ──

export const MESSAGE_MAX = 2000;
export const MAX_ATTACHMENTS = 4;
export const CSAT_COMMENT_MAX = 500;
export const LOST_ITEM_MIN = 3;
export const LOST_ITEM_MAX = 500;
/** Characters before the help search asks the server. */
export const SEARCH_MIN = 2;

export const DEFAULT_SUPPORT = {
  response_promise_es: 'Respondemos en menos de 24 horas.',
  response_promise_en: 'We answer within 24 hours.',
  auto_close_days: 7,
  lost_item_days: 7,
  lost_item_chat_hours: 72,
};

/** "Respondemos en menos de 24 horas." in the app's language, as configured from the admin. */
export function responsePromise(config: Pick<AppConfig, 'support'> | null | undefined, language: string): string {
  const english = language.toLowerCase().startsWith('en');
  const support = config?.support;
  const value = english ? support?.response_promise_en : support?.response_promise_es;
  return value?.trim() || (english ? DEFAULT_SUPPORT.response_promise_en : DEFAULT_SUPPORT.response_promise_es);
}

// ── Help center ──

/** Topics in the order the help home shows them. */
export const HELP_TOPICS: readonly HelpTopic[] = ['account', 'rides', 'payments', 'wallet', 'safety', 'documents', 'app'];

export function isHelpTopic(value: unknown): value is HelpTopic {
  return typeof value === 'string' && (HELP_TOPICS as readonly string[]).includes(value);
}

/** Articles for the current mode: drivers also see the driver articles (the API filters again). */
export const helpAudienceFor = (mode: 'passenger' | 'driver' | null | undefined): Exclude<HelpAudience, 'all'> =>
  mode === 'driver' ? 'driver' : 'passenger';

/** Only `en` has its own articles; anything else asks for Spanish (the API falls back to Spanish too). */
export const helpLocaleFor = (language: string): 'es' | 'en' => (language.toLowerCase().startsWith('en') ? 'en' : 'es');

/** Topics that have articles, in HELP_TOPICS order, each with its articles by position. */
export function groupByTopic(articles: readonly HelpArticleSummary[]): { topic: HelpTopic; articles: HelpArticleSummary[] }[] {
  return HELP_TOPICS.map((topic) => ({
    topic,
    articles: articles.filter((a) => a.topic === topic).sort((a, b) => a.position - b.position),
  })).filter((group) => group.articles.length > 0);
}

/** The text worth searching ("" until it has SEARCH_MIN characters). */
export function searchTerm(value: string): string {
  const term = value.trim().replace(/\s+/g, ' ');
  return term.length >= SEARCH_MIN ? term : '';
}

export type ArticleLink = { kind: 'external'; url: string } | { kind: 'article'; slug: string } | null;

/**
 * Where a link in an article goes: web, mail and phone links open outside; a bare slug or "/help/slug"
 * opens that article inside the app. Anything else is ignored.
 */
export function articleLink(href: string): ArticleLink {
  const value = href.trim();
  if (/^(https?:|mailto:|tel:)/i.test(value)) return { kind: 'external', url: value };
  const slug = value.replace(/^\/?(help\/)?(articles\/)?/, '').replace(/\/$/, '');
  if (/^[a-z0-9-]+$/.test(slug)) return { kind: 'article', slug };
  return null;
}

// ── Conversations ──

export type ConversationState = 'replied' | 'waiting' | 'closed';

const isClosed = (report: Pick<Report, 'status'>) => !isOpenReport(report.status);

/**
 * "Te respondimos" (the team is waiting for the user), "Esperando respuesta" (waiting for the team) or closed.
 * Older servers without `waiting_on`: open reports read as waiting for the team.
 */
export function conversationState(report: Pick<Report, 'status' | 'waiting_on'>): ConversationState {
  if (isClosed(report)) return 'closed';
  return report.waiting_on === 'user' ? 'replied' : 'waiting';
}

/** The unread dot: the team wrote after the user last opened it. */
export const isUnread = (report: Pick<Report, 'unread'>) => report.unread === true;

export const unreadCount = (reports: readonly Pick<Report, 'unread'>[]) => reports.filter(isUnread).length;

/** Can the user still write? Without `can_reply` (older servers) only open reports take replies. */
export const canReply = (report: Pick<Report, 'status' | 'can_reply'>) =>
  typeof report.can_reply === 'boolean' ? report.can_reply : !isClosed(report);

/** The CSAT card: the API says when (closed and not rated yet). */
export const canRate = (report: Pick<Report, 'can_rate' | 'csat'>) => report.can_rate === true && report.csat == null;

/** Most recent activity, for "hace 2 h" in the list. */
export const lastActivity = (report: Pick<Report, 'last_message_at' | 'updated_at' | 'created_at'>) =>
  report.last_message_at ?? report.updated_at ?? report.created_at;

/**
 * The thread for servers without GET /reports/me/{id}/messages: the description as the user's first message
 * and the team's final answer, if any.
 */
export function fallbackMessages(report: Report): ReportMessage[] {
  const messages: ReportMessage[] = [
    {
      id: `${report.id}-description`,
      author_kind: 'user',
      author_name: null,
      mine: true,
      body: report.description,
      attachments: [],
      created_at: report.created_at,
    },
  ];
  if (isClosed(report) && report.resolution?.trim()) {
    messages.push({
      id: `${report.id}-resolution`,
      author_kind: 'staff',
      author_name: null,
      mine: false,
      body: report.resolution.trim(),
      attachments: [],
      created_at: report.resolved_at ?? report.updated_at,
    });
  }
  return messages;
}

/** Adds a message once (the POST answer and a refetch can both bring it), oldest first. */
export function appendMessage(messages: readonly ReportMessage[] | undefined, message: ReportMessage): ReportMessage[] {
  const list = messages ?? [];
  if (list.some((m) => m.id === message.id)) return [...list];
  return [...list, message].sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export type MessageProblem = 'empty' | 'too_long' | null;

export function messageProblem(text: string): MessageProblem {
  const length = text.trim().length;
  if (!length) return 'empty';
  if (length > MESSAGE_MAX) return 'too_long';
  return null;
}

// ── Lost item ──

export type LostItemState = 'waiting' | 'chat' | 'has_it' | 'not_found';

/** Waiting for the driver, "Lo tiene" with the chat open, "Lo tiene" after the chat closed, or not found. */
export function lostItemState(item: Pick<LostItem, 'answer' | 'chat_open'>): LostItemState {
  if (item.answer === 'not_found') return 'not_found';
  if (item.answer === 'has_it') return item.chat_open ? 'chat' : 'has_it';
  return 'waiting';
}

export function lostItemProblem(text: string): 'too_short' | 'too_long' | null {
  const length = text.trim().length;
  if (length < LOST_ITEM_MIN) return 'too_short';
  if (length > LOST_ITEM_MAX) return 'too_long';
  return null;
}

/** The passenger can still ask for a lost item: within `lost_item_days` of the end of a completed ride. */
export function lostItemAllowed(
  ride: Pick<Ride, 'status' | 'driver' | 'completed_at'>,
  config: Pick<AppConfig, 'support'> | null | undefined,
  now: Date = new Date(),
): boolean {
  if (ride.status !== 'completed' || !ride.driver) return false;
  if (!ride.completed_at) return true;
  const days = config?.support?.lost_item_days ?? DEFAULT_SUPPORT.lost_item_days;
  return now.getTime() - new Date(ride.completed_at).getTime() <= days * 86_400_000;
}

// ── "Necesito ayuda con este viaje" ──

export type RideHelpOption = 'lost_item' | 'fare' | 'no_show' | 'other';

/**
 * Guided flows from a ride's detail. Every report about a ride needs a driver (409 ride_without_driver):
 * a ride that never had one offers nothing. Lost item: the passenger of a completed ride (in time). Fare: a
 * completed ride. No show: "El motorizado no llegó" / "El pasajero no se presentó" on a ride that had a
 * driver and was cancelled.
 */
export function rideHelpOptions(
  ride: Pick<Ride, 'status' | 'driver' | 'completed_at'>,
  role: 'passenger' | 'driver',
  config?: Pick<AppConfig, 'support'> | null,
  now: Date = new Date(),
): RideHelpOption[] {
  if (!ride.driver) return [];
  const options: RideHelpOption[] = [];
  if (role === 'passenger' && lostItemAllowed(ride, config, now)) options.push('lost_item');
  if (ride.status === 'completed') options.push('fare');
  else if (ride.status.startsWith('cancelled')) options.push('no_show');
  options.push('other');
  return options;
}

// ── Notifications ──

type Payload = {
  type?: unknown;
  kind?: unknown;
  event?: unknown;
  ride_id?: unknown;
  report_id?: unknown;
  data?: { type?: unknown; kind?: unknown; event?: unknown; ride_id?: unknown; report_id?: unknown } | null;
} | null;

const field = (payload: unknown, key: 'type' | 'kind' | 'event' | 'ride_id' | 'report_id') => {
  const record = payload as Payload;
  const value = record?.[key] ?? record?.data?.[key];
  return typeof value === 'string' && value ? value : null;
};

const tagOf = (payload: unknown) => field(payload, 'kind') ?? field(payload, 'type');

/** Lost item pushes: {type: "lost_item", event: "lost_item_asked" | "lost_item_found" | "lost_item_not_found", ride_id}. */
export function isLostItemNotification(payload: unknown): boolean {
  const tag = tagOf(payload);
  const event = field(payload, 'event');
  return tag === 'lost_item' || (!!event && event.startsWith('lost_item'));
}

export const lostItemRideIdOf = (payload: unknown) => (isLostItemNotification(payload) ? field(payload, 'ride_id') : null);

/** Support pushes ({type: "support", event, report_id}) and the older {type: "report", report_id}. */
export function isSupportNotification(payload: unknown): boolean {
  const tag = tagOf(payload);
  return tag === 'support' || (tag !== null && tag.startsWith('report'));
}

export type SupportHref =
  | { pathname: '/reports/[id]'; params: { id: string } }
  | { pathname: '/ride/lost-item'; params: { id: string } };

/**
 * Where tapping a support or lost item notification goes: the conversation, or the ride's lost item screen
 * (the driver answers "Lo tengo / No lo tengo" there; the passenger sees the answer and opens the chat).
 */
export function supportHrefOf(payload: unknown): SupportHref | null {
  const rideId = lostItemRideIdOf(payload);
  if (rideId) return { pathname: '/ride/lost-item', params: { id: rideId } };
  const reportId = field(payload, 'report_id');
  if (reportId && (isSupportNotification(payload) || !tagOf(payload))) return { pathname: '/reports/[id]', params: { id: reportId } };
  return null;
}
