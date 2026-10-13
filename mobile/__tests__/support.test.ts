import { describe, expect, it } from '@jest/globals';

import { parseInline, parseMarkdown } from '@/lib/legal';
import {
  appendMessage,
  articleLink,
  canRate,
  canReply,
  conversationState,
  fallbackMessages,
  groupByTopic,
  helpAudienceFor,
  helpLocaleFor,
  isLostItemNotification,
  isSupportNotification,
  isUnread,
  lostItemAllowed,
  lostItemProblem,
  lostItemState,
  messageProblem,
  responsePromise,
  rideHelpOptions,
  searchTerm,
  supportHrefOf,
  unreadCount,
} from '@/lib/support';
import type { HelpArticleSummary, Report, ReportMessage } from '@/lib/types';

const report = (overrides: Partial<Report> = {}): Report => ({
  id: 'r1',
  category: 'app_issue',
  description: 'La app se cierra al abrir el mapa',
  status: 'open',
  priority: 'normal',
  ride_id: null,
  reporter_role: null,
  created_at: '2026-10-01T10:00:00Z',
  updated_at: '2026-10-01T10:00:00Z',
  resolution: null,
  resolved_at: null,
  ...overrides,
});

describe('markdown for help articles', () => {
  it('parses links, alone or in bold, next to bold text', () => {
    expect(parseInline('Lee **esto** y [la guía](https://kuulis.com/ayuda).')).toEqual([
      { text: 'Lee ', bold: false },
      { text: 'esto', bold: true },
      { text: ' y ', bold: false },
      { text: 'la guía', bold: false, href: 'https://kuulis.com/ayuda' },
      { text: '.', bold: false },
    ]);
    expect(parseInline('**[Pagar](pagar-cuota)**')).toEqual([{ text: 'Pagar', bold: true, href: 'pagar-cuota' }]);
  });

  it('keeps text without links unchanged', () => {
    expect(parseInline('Sin enlaces [ni cierre')).toEqual([{ text: 'Sin enlaces [ni cierre', bold: false }]);
  });

  it('parses headings, numbered and bullet lists with links', () => {
    const blocks = parseMarkdown('# Cambiar el correo\n\n1. Abre **Perfil**\n2. Toca [Editar](editar-perfil)\n\n- Uno\n- Dos');
    expect(blocks.map((b) => b.type)).toEqual(['heading', 'list', 'list']);
    expect(blocks[1]).toMatchObject({ ordered: true });
    expect(blocks[2]).toMatchObject({ ordered: false });
    const ordered = blocks[1] as { items: { href?: string }[][] };
    expect(ordered.items[1].some((span) => span.href === 'editar-perfil')).toBe(true);
  });
});

describe('articleLink', () => {
  it('opens web, mail and phone links outside', () => {
    expect(articleLink('https://wa.me/584121234567')).toEqual({ kind: 'external', url: 'https://wa.me/584121234567' });
    expect(articleLink('mailto:soporte@kuulis.com')).toEqual({ kind: 'external', url: 'mailto:soporte@kuulis.com' });
  });

  it('opens other articles in the app', () => {
    expect(articleLink('pagar-cuota')).toEqual({ kind: 'article', slug: 'pagar-cuota' });
    expect(articleLink('/help/pagar-cuota')).toEqual({ kind: 'article', slug: 'pagar-cuota' });
  });

  it('ignores anything else', () => {
    expect(articleLink('javascript:alert(1)')).toBeNull();
    expect(articleLink('../../etc')).toBeNull();
  });
});

describe('help center', () => {
  const article = (id: string, topic: HelpArticleSummary['topic'], position: number): HelpArticleSummary => ({
    id,
    slug: id,
    locale: 'es',
    topic,
    audience: 'all',
    title: id,
    excerpt: '',
    position,
    updated_at: '2026-10-01T00:00:00Z',
  });

  it('groups by topic in the fixed order, by position, skipping empty topics', () => {
    const groups = groupByTopic([article('b', 'wallet', 2), article('a', 'account', 1), article('c', 'wallet', 1)]);
    expect(groups.map((g) => g.topic)).toEqual(['account', 'wallet']);
    expect(groups[1].articles.map((a) => a.id)).toEqual(['c', 'b']);
  });

  it('asks for the mode audience and es/en', () => {
    expect(helpAudienceFor('driver')).toBe('driver');
    expect(helpAudienceFor('passenger')).toBe('passenger');
    expect(helpAudienceFor(null)).toBe('passenger');
    expect(helpLocaleFor('en-US')).toBe('en');
    expect(helpLocaleFor('es-VE')).toBe('es');
  });

  it('searches from two characters, trimmed', () => {
    expect(searchTerm(' a ')).toBe('');
    expect(searchTerm('  pagar   cuota ')).toBe('pagar cuota');
  });

  it('uses the configured response promise, with defaults', () => {
    expect(responsePromise({ support: { response_promise_es: 'En 2 horas.', response_promise_en: 'In 2 hours.' } }, 'es')).toBe(
      'En 2 horas.',
    );
    expect(responsePromise({ support: { response_promise_en: 'In 2 hours.' } }, 'en')).toBe('In 2 hours.');
    expect(responsePromise({}, 'es')).toBe('Respondemos en menos de 24 horas.');
    expect(responsePromise(null, 'en')).toBe('We answer within 24 hours.');
  });
});

describe('conversations', () => {
  it('labels: we answered, waiting for the team, closed', () => {
    expect(conversationState(report({ waiting_on: 'user' }))).toBe('replied');
    expect(conversationState(report({ waiting_on: 'staff' }))).toBe('waiting');
    expect(conversationState(report())).toBe('waiting');
    expect(conversationState(report({ status: 'resolved', waiting_on: null }))).toBe('closed');
    expect(conversationState(report({ status: 'dismissed', waiting_on: 'user' }))).toBe('closed');
  });

  it('counts unread conversations', () => {
    expect(isUnread(report({ unread: true }))).toBe(true);
    expect(isUnread(report())).toBe(false);
    expect(unreadCount([report({ unread: true }), report(), report({ unread: true })])).toBe(2);
  });

  it('replies follow can_reply, else only open reports', () => {
    expect(canReply(report({ status: 'resolved', can_reply: true }))).toBe(true);
    expect(canReply(report({ can_reply: false }))).toBe(false);
    expect(canReply(report({ status: 'in_review' }))).toBe(true);
    expect(canReply(report({ status: 'resolved' }))).toBe(false);
  });

  it('asks for a rating only when the API allows it and none was given', () => {
    expect(canRate(report({ can_rate: true }))).toBe(true);
    expect(canRate(report({ can_rate: true, csat: 4 }))).toBe(false);
    expect(canRate(report())).toBe(false);
  });

  it('builds a thread for servers without messages', () => {
    expect(fallbackMessages(report()).map((m) => m.body)).toEqual(['La app se cierra al abrir el mapa']);
    const closed = fallbackMessages(
      report({ status: 'resolved', resolution: ' Ya lo arreglamos. ', resolved_at: '2026-10-02T10:00:00Z' }),
    );
    expect(closed.map((m) => [m.mine, m.body])).toEqual([
      [true, 'La app se cierra al abrir el mapa'],
      [false, 'Ya lo arreglamos.'],
    ]);
  });

  it('appends a message once, in time order', () => {
    const message = (id: string, at: string): ReportMessage => ({
      id,
      author_kind: 'user',
      author_name: null,
      mine: true,
      body: id,
      attachments: [],
      created_at: at,
    });
    const list = [message('a', '2026-10-01T10:00:00Z'), message('c', '2026-10-01T12:00:00Z')];
    expect(appendMessage(list, message('b', '2026-10-01T11:00:00Z')).map((m) => m.id)).toEqual(['a', 'b', 'c']);
    expect(appendMessage(list, message('a', '2026-10-01T10:00:00Z'))).toHaveLength(2);
    expect(appendMessage(undefined, message('a', '2026-10-01T10:00:00Z'))).toHaveLength(1);
  });

  it('checks the reply length', () => {
    expect(messageProblem('   ')).toBe('empty');
    expect(messageProblem('ok')).toBeNull();
    expect(messageProblem('x'.repeat(2001))).toBe('too_long');
  });
});

describe('lost item', () => {
  it('maps the answer and the chat to a state', () => {
    expect(lostItemState({ answer: null, chat_open: false })).toBe('waiting');
    expect(lostItemState({ answer: 'has_it', chat_open: true })).toBe('chat');
    expect(lostItemState({ answer: 'has_it', chat_open: false })).toBe('has_it');
    expect(lostItemState({ answer: 'not_found', chat_open: false })).toBe('not_found');
  });

  it('checks the description', () => {
    expect(lostItemProblem(' ab ')).toBe('too_short');
    expect(lostItemProblem('mochila')).toBeNull();
    expect(lostItemProblem('x'.repeat(501))).toBe('too_long');
  });

  const driver = { id: 'd1', first_name: 'Luis' } as never;
  const now = new Date('2026-10-10T12:00:00Z');

  it('is allowed within lost_item_days of a completed ride with a driver', () => {
    const ride = { status: 'completed' as const, driver, completed_at: '2026-10-05T12:00:00Z' };
    expect(lostItemAllowed(ride, null, now)).toBe(true);
    expect(lostItemAllowed(ride, { support: { lost_item_days: 3 } }, now)).toBe(false);
    expect(lostItemAllowed({ ...ride, driver: null }, null, now)).toBe(false);
    expect(lostItemAllowed({ ...ride, status: 'cancelled_by_driver' }, null, now)).toBe(false);
  });

  it('offers the guided flows that apply to the ride', () => {
    const completed = { status: 'completed' as const, driver, completed_at: '2026-10-09T12:00:00Z' };
    expect(rideHelpOptions(completed, 'passenger', null, now)).toEqual(['lost_item', 'fare', 'other']);
    expect(rideHelpOptions(completed, 'driver', null, now)).toEqual(['fare', 'other']);
    const cancelled = { status: 'cancelled_by_driver' as const, driver, completed_at: null };
    expect(rideHelpOptions(cancelled, 'passenger', null, now)).toEqual(['no_show', 'other']);
    expect(rideHelpOptions({ ...cancelled, driver: null }, 'passenger', null, now)).toEqual([]);
    expect(rideHelpOptions({ ...cancelled, status: 'in_progress' }, 'passenger', null, now)).toEqual(['other']);
  });
});

describe('notifications', () => {
  it('opens the conversation for support and older report pushes', () => {
    expect(supportHrefOf({ type: 'support', event: 'support_reply', report_id: 'r1' })).toEqual({
      pathname: '/reports/[id]',
      params: { id: 'r1' },
    });
    expect(supportHrefOf({ data: { type: 'report', report_id: 'r2' } })).toEqual({ pathname: '/reports/[id]', params: { id: 'r2' } });
    expect(isSupportNotification({ kind: 'support', report_id: 'r1' })).toBe(true);
  });

  it('opens the lost item screen of the ride', () => {
    const asked = { type: 'lost_item', event: 'lost_item_asked', ride_id: 'ride1' };
    expect(isLostItemNotification(asked)).toBe(true);
    expect(supportHrefOf(asked)).toEqual({ pathname: '/ride/lost-item', params: { id: 'ride1' } });
    expect(supportHrefOf({ data: { type: 'lost_item', event: 'lost_item_found', ride_id: 'ride2' } })).toEqual({
      pathname: '/ride/lost-item',
      params: { id: 'ride2' },
    });
  });

  it('ignores other notifications', () => {
    expect(supportHrefOf({ type: 'ride.completed', ride_id: 'x' })).toBeNull();
    expect(supportHrefOf({ type: 'driver_status' })).toBeNull();
    expect(supportHrefOf(null)).toBeNull();
  });
});
