import { describe, expect, it } from '@jest/globals';

import { channelFor, checksumMatches, downloadFraction, formatMegabytes, parseBuild } from '@/lib/appVersion';

describe('app version', () => {
  it('maps the app environment to a release channel', () => {
    expect(channelFor('production')).toBe('production');
    expect(channelFor('qa')).toBe('qa');
    expect(channelFor('local')).toBe('qa');
  });

  it('reads the Android versionCode, 0 when there is none', () => {
    expect(parseBuild('42')).toBe(42);
    expect(parseBuild(null)).toBe(0);
    expect(parseBuild(undefined)).toBe(0);
    expect(parseBuild('')).toBe(0);
    expect(parseBuild('1.0')).toBe(1);
    expect(parseBuild('abc')).toBe(0);
    expect(parseBuild('-3')).toBe(0);
  });

  it('formats sizes in MB', () => {
    expect(formatMegabytes(12_345_678)).toBe('12.3');
    expect(formatMegabytes(0)).toBe('0.0');
  });

  it('accepts only an APK with the published size and MD5', () => {
    const release = { size: 1000, md5: 'ABCDEF0123' };
    expect(checksumMatches({ size: 1000, md5: 'abcdef0123' }, release)).toBe(true);
    expect(checksumMatches({ size: 999, md5: 'abcdef0123' }, release)).toBe(false);
    expect(checksumMatches({ size: 1000, md5: 'ffffff0123' }, release)).toBe(false);
    expect(checksumMatches({ size: 1000 }, release)).toBe(false);
    expect(checksumMatches({ size: 1000, md5: null }, release)).toBe(false);
  });

  it('computes download progress with or without Content-Length', () => {
    expect(downloadFraction(50, 200, 1000)).toBe(0.25);
    expect(downloadFraction(500, -1, 1000)).toBe(0.5);
    expect(downloadFraction(2000, -1, 1000)).toBe(1);
    expect(downloadFraction(10, -1, 0)).toBe(0);
  });
});
