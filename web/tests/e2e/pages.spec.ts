import { expect, test } from '@playwright/test'

// The secondary pages keep working after their redesign (docs/website-redesign/07 M7): the contact form sends, the
// help search filters, the APK link and fingerprint match the API, and the one-task pages show their dead-end
// states. Requests the browser makes are answered here, so these run without the API.
test.use({ locale: 'es-VE' })

test('contact: the form solves the challenge and sends', async ({ page }) => {
  await page.route('**/api/v1/public/contact/challenge', route => route.fulfill({ json: { challenge: 'abc', difficulty: 1, expires_in: 300 } }))
  let sent: Record<string, unknown> | null = null
  await page.route('**/api/v1/public/contact', (route) => {
    sent = route.request().postDataJSON()
    return route.fulfill({ status: 202, json: {} })
  })
  await page.goto('/contacto', { waitUntil: 'networkidle' })
  await page.getByLabel('Tu nombre').fill('Ana Pérez')
  await page.getByLabel('Tu email').fill('ana@example.com')
  await page.getByLabel('Tu mensaje').fill('No puedo entrar a mi cuenta desde ayer, me dice que la clave es incorrecta.')
  await page.getByRole('button', { name: 'Enviar mensaje' }).click()
  await expect(page.getByRole('status')).toContainText('¡Mensaje enviado!')
  expect(sent).toMatchObject({ email: 'ana@example.com', category: 'app_issue', challenge: 'abc' })
})

test('help: searching asks the API for the term and lists what it returns', async ({ page }) => {
  const article = { id: '1', slug: 'olvide-mi-clave', locale: 'es', topic: 'account', audience: 'all', title: 'Olvidé mi contraseña', excerpt: 'Toca Olvidé mi contraseña.', position: 1, updated_at: '2026-10-01T00:00:00Z' }
  await page.route('**/api/v1/help/articles**', (route) => {
    const q = new URL(route.request().url()).searchParams.get('q')
    return route.fulfill({ json: q === 'clave' ? [article] : [] })
  })
  await page.goto('/ayuda', { waitUntil: 'networkidle' })
  await page.getByRole('searchbox').fill('clave')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page.getByRole('heading', { name: 'Resultados para «clave»' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Olvidé mi contraseña/ })).toHaveAttribute('href', '/ayuda/olvide-mi-clave')
})

test('download: the button fetches the published APK and the fingerprint is its SHA-256', async ({ page, request }) => {
  await page.goto('/descargar', { waitUntil: 'networkidle' })
  const button = page.getByRole('link', { name: 'Descargar Kuulis (APK)' })
  test.skip(await button.count() === 0, 'no release published without the API')
  await expect(button).toHaveAttribute('href', '/api/v1/app/download')
  // A local build reads the API from elsewhere (E2E_API_URL); a deployed site serves it under /api.
  const { latest } = await (await request.get(`${process.env.E2E_API_URL ?? ''}/api/v1/app/version`)).json()
  await page.getByText('Huella de seguridad (SHA-256)').click()
  await expect(page.locator('.fingerprint code')).toHaveText(latest.sha256)
})

test('download: an iPhone sees its answer before the APK', async ({ browser }) => {
  const context = await browser.newContext({ locale: 'es-VE', userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' })
  const page = await context.newPage()
  await page.goto('/descargar', { waitUntil: 'networkidle' })
  const cards = page.locator('.side .card')
  await expect(cards.first()).toHaveClass(/iphone/)
  await context.close()
})

test('one-task pages: an unknown invitation and a dead ride link say so and offer a way on', async ({ page }) => {
  await page.goto('/i/ZZZ999', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Esta invitación no existe')
  await expect(page.locator('main a[href="/motorizados"]')).toBeVisible()
  await page.route('**/api/v1/**', route => route.fulfill({ status: 404, json: { detail: 'not found' } }))
  await page.goto('/v/abc', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Enlace no válido')
})
