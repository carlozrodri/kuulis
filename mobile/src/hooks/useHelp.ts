import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api } from '@/lib/api';
import { helpAudienceFor, helpLocaleFor } from '@/lib/support';
import type { HelpArticle, HelpArticleSummary, HelpTopic } from '@/lib/types';
import { useMode } from '@/providers/ModeProvider';

/** Help center (doc 13): public articles, read with or without a session. */
export const helpKeys = {
  all: ['help'] as const,
  list: (locale: string, audience: string, topic: string, q: string) => ['help', 'list', locale, audience, topic, q] as const,
  article: (slug: string, locale: string) => ['help', 'article', slug, locale] as const,
};

/** `value` once it has stopped changing for `delay` ms (the search box). */
export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** The locale and audience (passenger or driver, from the current mode) the help center asks for. */
export function useHelpContext() {
  const { i18n } = useTranslation();
  const { mode } = useMode();
  return { locale: helpLocaleFor(i18n.language), audience: helpAudienceFor(mode) };
}

/** GET /help/articles: published articles for this audience, by topic and position; `q` searches. */
export function useHelpArticles({ topic, q }: { topic?: HelpTopic; q?: string } = {}) {
  const { locale, audience } = useHelpContext();
  return useQuery({
    queryKey: helpKeys.list(locale, audience, topic ?? '', q ?? ''),
    queryFn: ({ signal }) =>
      api<HelpArticleSummary[]>('/help/articles', { query: { locale, audience, topic, q: q || undefined }, signal }),
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
  });
}

/** GET /help/articles/{slug} (falls back to Spanish when there is no translation). */
export function useHelpArticle(slug: string | undefined) {
  const { locale } = useHelpContext();
  return useQuery({
    queryKey: helpKeys.article(slug ?? '', locale),
    queryFn: () => api<HelpArticle>(`/help/articles/${encodeURIComponent(slug!)}`, { query: { locale } }),
    enabled: !!slug,
    staleTime: 5 * 60_000,
  });
}

/** POST /help/articles/{id}/feedback: "¿Te ayudó?". */
export function useHelpFeedback() {
  return useMutation({
    mutationFn: ({ id, helpful }: { id: string; helpful: boolean }) =>
      api<void>(`/help/articles/${id}/feedback`, { method: 'POST', body: { helpful } }),
  });
}
