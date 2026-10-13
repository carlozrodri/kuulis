import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { checkNonce, leadingZeroBits, sha256 as jsSha256, solveChallenge } from '../app/utils/pow'

const sha256 = (text: string) => new Uint8Array(createHash('sha256').update(text).digest())

describe('proof of work', () => {
  it('counts leading zero bits', () => {
    expect(leadingZeroBits(new Uint8Array([0xff]))).toBe(0)
    expect(leadingZeroBits(new Uint8Array([0x01, 0xff]))).toBe(7)
    expect(leadingZeroBits(new Uint8Array([0x00, 0x00, 0x20]))).toBe(18)
    expect(leadingZeroBits(new Uint8Array([0, 0]))).toBe(16)
  })

  it('hashes like node:crypto', () => {
    for (const text of ['', 'abc', 'a'.repeat(55), 'a'.repeat(56), 'a'.repeat(64), 'ñandú:12345', 'x'.repeat(200)]) {
      expect(Buffer.from(jsSha256(new TextEncoder().encode(text))).toString('hex'))
        .toBe(Buffer.from(sha256(text)).toString('hex'))
    }
  })

  it('finds the first nonce that meets the difficulty, as the API checks it', async () => {
    const challenge = 'abc123.1760000000'
    const nonce = await solveChallenge(challenge, 10, { chunk: 64 })
    expect(leadingZeroBits(sha256(`${challenge}:${nonce}`))).toBeGreaterThanOrEqual(10)
    for (let n = 0; n < Number(nonce); n++) {
      expect(leadingZeroBits(sha256(`${challenge}:${n}`))).toBeLessThan(10)
    }
    expect(await checkNonce(challenge, nonce, 10)).toBe(true)
  })

  it('stops when aborted', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(solveChallenge('x', 40, { signal: controller.signal })).rejects.toThrow()
  })
})
