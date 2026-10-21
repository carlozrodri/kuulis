/**
 * The API base as an absolute URL. `apiBase` is a path when the site and the API share the host (Coolify), or a
 * full URL when they don't (the site on Cloudflare Workers, the API on its own host).
 */
export function absoluteApiBase(apiBase: string, origin: string): string {
  return /^https?:\/\//.test(apiBase) ? apiBase : `${origin}${apiBase}`
}
