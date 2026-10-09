import { describe, expect, it } from "@jest/globals";

import {
  canDriverCancel,
  canPassengerCancel,
  countdownProgress,
  decodePolyline,
  estimateEtaSeconds,
  formatClock,
  formatDistance,
  formatDuration,
  formatFare,
  formatPlate,
  formatRating,
  formatSurge,
  googleMapsAppUrl,
  hasSurge,
  haversineMeters,
  inServiceArea,
  isActiveStatus,
  isChatOpen,
  isTerminalStatus,
  mergeRide,
  nextDriverAction,
  placeFromGeo,
  rideRole,
  rideRoleStrict,
  rideStep,
  secondsSince,
  secondsUntil,
  shortAddress,
  wazeNavigationUrl,
} from "@/lib/ride";
import type { Ride } from "@/lib/types";

/** Reference encoder (Google polyline algorithm) to build fixtures at any precision. */
function encode(points: [number, number][], precision = 5) {
  const factor = 10 ** precision;
  let out = "";
  let prevLat = 0;
  let prevLng = 0;
  const encodeValue = (value: number) => {
    let v = value < 0 ? ~(value << 1) : value << 1;
    let chunk = "";
    while (v >= 0x20) {
      chunk += String.fromCharCode((0x20 | (v & 0x1f)) + 63);
      v >>= 5;
    }
    return chunk + String.fromCharCode(v + 63);
  };
  for (const [lat, lng] of points) {
    const la = Math.round(lat * factor);
    const ln = Math.round(lng * factor);
    out += encodeValue(la - prevLat) + encodeValue(ln - prevLng);
    prevLat = la;
    prevLng = ln;
  }
  return out;
}

describe("decodePolyline", () => {
  it("decodes the Google reference polyline", () => {
    expect(decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")).toEqual([
      { latitude: 38.5, longitude: -120.2 },
      { latitude: 40.7, longitude: -120.95 },
      { latitude: 43.252, longitude: -126.453 },
    ]);
  });

  it("returns [] for empty input", () => {
    expect(decodePolyline(null)).toEqual([]);
    expect(decodePolyline("")).toEqual([]);
  });

  it("round-trips a Caracas route at precision 5", () => {
    const route: [number, number][] = [
      [10.49962, -66.88264],
      [10.50011, -66.87512],
      [10.4917, -66.8531],
    ];
    const decoded = decodePolyline(encode(route));
    decoded.forEach((p, i) => {
      expect(p.latitude).toBeCloseTo(route[i][0], 5);
      expect(p.longitude).toBeCloseTo(route[i][1], 5);
    });
  });

  it("detects OSRM polyline6 (precision 6) automatically", () => {
    const route: [number, number][] = [
      [10.499621, -66.882641],
      [10.491703, -66.853101],
    ];
    const decoded = decodePolyline(encode(route, 6));
    expect(decoded[0].latitude).toBeCloseTo(10.499621, 6);
    expect(decoded[1].longitude).toBeCloseTo(-66.853101, 6);
  });

  it("ignores a truncated tail instead of throwing", () => {
    const full = encode([
      [10.5, -66.9],
      [10.51, -66.91],
    ]);
    expect(decodePolyline(full.slice(0, -2)).length).toBe(1);
  });
});

describe("formatting", () => {
  it("formats USD fares with two decimals", () => {
    expect(formatFare("2.4")).toBe("$2.40");
    expect(formatFare("12.00")).toBe("$12.00");
    expect(formatFare(3)).toBe("$3.00");
    expect(formatFare(undefined)).toBe("$—");
  });

  it("formats distances in m and km", () => {
    expect(formatDistance(4)).toBe("10 m");
    expect(formatDistance(846)).toBe("850 m");
    expect(formatDistance(3240, "en")).toBe("3.2 km");
    expect(formatDistance(3240, "es")).toBe("3,2 km");
    expect(formatDistance(12_600, "en")).toBe("13 km");
    expect(formatDistance(-1)).toBe("—");
  });

  it("formats durations without ever showing 0 min", () => {
    expect(formatDuration(5)).toBe("1 min");
    expect(formatDuration(600)).toBe("10 min");
    expect(formatDuration(3600)).toBe("1 h");
    expect(formatDuration(3900)).toBe("1 h 05 min");
    expect(formatDuration(Number.NaN)).toBe("—");
  });

  it("formats clocks, ratings, surge and plates", () => {
    expect(formatClock(75)).toBe("1:15");
    expect(formatClock(5)).toBe("0:05");
    expect(formatRating("4.86")).toBe("4.9");
    expect(formatRating(null)).toBeNull();
    expect(formatRating(0)).toBeNull();
    expect(hasSurge("1.00")).toBe(false);
    expect(hasSurge("1.20")).toBe(true);
    expect(formatSurge("1.20")).toBe("×1.2");
    expect(formatSurge("1.25")).toBe("×1.25");
    expect(formatSurge("2.00")).toBe("×2");
    expect(formatPlate("ab2c34d")).toBe("AB2 C34D");
    expect(formatPlate("AB12")).toBe("AB12");
  });

  it("shortens addresses and builds places from geo results", () => {
    expect(shortAddress("Centro Sambil, Av. Libertador, Caracas")).toBe(
      "Centro Sambil",
    );
    expect(
      placeFromGeo({
        name: "Sambil",
        address: "Av. Libertador, Caracas",
        lat: 1,
        lng: 2,
      }),
    ).toEqual({
      lat: 1,
      lng: 2,
      address: "Sambil, Av. Libertador, Caracas",
    });
    expect(
      placeFromGeo({
        name: "Sambil",
        address: "Sambil, Caracas",
        lat: 1,
        lng: 2,
      }).address,
    ).toBe("Sambil, Caracas");
    expect(
      placeFromGeo({ name: "Sambil", address: "", lat: 1, lng: 2 }).address,
    ).toBe("Sambil");
  });
});

describe("time helpers", () => {
  const now = Date.parse("2026-10-09T12:00:00Z");
  it("counts down to expires_at", () => {
    expect(secondsUntil("2026-10-09T12:00:15Z", now)).toBe(15);
    expect(secondsUntil("2026-10-09T12:00:14.2Z", now)).toBe(15);
    expect(secondsUntil("2026-10-09T11:59:00Z", now)).toBe(0);
    expect(secondsUntil(null, now)).toBe(0);
    expect(countdownProgress("2026-10-09T12:00:15Z", 15, now)).toBe(1);
    expect(countdownProgress("2026-10-09T12:00:03Z", 15, now)).toBeCloseTo(0.2);
    expect(secondsSince("2026-10-09T11:59:18Z", now)).toBe(42);
  });
});

describe("geo", () => {
  const plazaVenezuela = { lat: 10.4996, lng: -66.8826 };
  const altamira = { lat: 10.4964, lng: -66.8486 };
  it("measures distances and estimates ETAs like the API fallback", () => {
    const d = haversineMeters(plazaVenezuela, altamira);
    expect(d).toBeGreaterThan(3600);
    expect(d).toBeLessThan(3800);
    // ×1.3 at 22 km/h ≈ 13 minutes.
    expect(estimateEtaSeconds(plazaVenezuela, altamira)).toBeGreaterThan(
      12 * 60,
    );
    expect(estimateEtaSeconds(plazaVenezuela, altamira)).toBeLessThan(14 * 60);
  });

  it("checks the service area boxes", () => {
    const caracas = {
      min_lat: 10.35,
      max_lat: 10.56,
      min_lng: -67.1,
      max_lng: -66.7,
    };
    const valencia = {
      min_lat: 39.4,
      max_lat: 39.55,
      min_lng: -0.45,
      max_lng: -0.3,
    };
    expect(inServiceArea(plazaVenezuela, [caracas])).toBe(true);
    expect(inServiceArea({ lat: 10.6, lng: -66.9 }, [caracas])).toBe(false);
    expect(
      inServiceArea({ lat: 39.47, lng: -0.376 }, [caracas, valencia]),
    ).toBe(true);
    expect(inServiceArea({ lat: 10.6, lng: -66.9 }, undefined)).toBe(true);
  });

  it("builds navigation links", () => {
    expect(wazeNavigationUrl(altamira)).toBe(
      "https://waze.com/ul?ll=10.4964,-66.8486&navigate=yes",
    );
    expect(googleMapsAppUrl(altamira, "android")).toBe(
      "google.navigation:q=10.4964,-66.8486&mode=d",
    );
    expect(googleMapsAppUrl(altamira, "ios")).toContain(
      "comgooglemaps://?daddr=10.4964,-66.8486",
    );
  });
});

describe("ride state", () => {
  it("classifies statuses", () => {
    expect(isActiveStatus("searching")).toBe(true);
    expect(isActiveStatus("completed")).toBe(false);
    expect(isTerminalStatus("no_drivers")).toBe(true);
    expect(isTerminalStatus("cancelled_by_admin")).toBe(true);
    expect(canPassengerCancel("cancelled_by_admin")).toBe(false);
    expect(isChatOpen("searching")).toBe(false);
    expect(isChatOpen("in_progress")).toBe(true);
    expect(canPassengerCancel("driver_arrived")).toBe(true);
    expect(canPassengerCancel("in_progress")).toBe(false);
    expect(canDriverCancel("searching")).toBe(false);
    expect(canDriverCancel("driver_assigned")).toBe(true);
  });

  it("gives the driver one next step at a time", () => {
    expect(nextDriverAction("driver_assigned")).toBe("arrive");
    expect(nextDriverAction("driver_arrived")).toBe("start");
    expect(nextDriverAction("in_progress")).toBe("complete");
    expect(nextDriverAction("completed")).toBeNull();
    expect(rideStep("in_progress")).toBeGreaterThan(rideStep("driver_arrived"));
  });

  const base = {
    id: "r1",
    status: "driver_assigned",
    passenger: { id: "u-pass", first_name: "Ana", rating: 4.9 },
    driver: {
      id: "u-driver",
      first_name: "Luis",
      rating: 4.8,
      photo_url: null,
      vehicle: null,
    },
    driver_location: { lat: 10.5, lng: -66.9, heading: 90 },
  } as unknown as Ride;

  it("knows which side of the ride the user is on", () => {
    expect(rideRole(base, "u-pass")).toBe("passenger");
    expect(rideRole(base, "u-driver")).toBe("driver");
    expect(rideRoleStrict(base, "someone-else")).toBeNull();
    expect(rideRole(base, "someone-else", "driver")).toBe("driver");
    expect(rideRoleStrict(base, undefined)).toBeNull();
  });

  it("never moves a ride backwards on out-of-order snapshots", () => {
    const arrived = {
      ...base,
      status: "driver_arrived",
      driver_location: null,
    } as Ride;
    const merged = mergeRide(arrived, {
      ...base,
      driver_location: { lat: 1, lng: 2, heading: null },
    });
    expect(merged.status).toBe("driver_arrived");
    expect(merged.driver_location).toEqual({ lat: 1, lng: 2, heading: null });
  });

  it("keeps the last known driver location when a snapshot has none", () => {
    const merged = mergeRide(base, {
      ...base,
      status: "driver_arrived",
      driver_location: null,
    } as Ride);
    expect(merged.status).toBe("driver_arrived");
    expect(merged.driver_location).toEqual(base.driver_location);
  });

  it("lets terminal statuses win and stick", () => {
    const cancelled = mergeRide(base, {
      ...base,
      status: "cancelled_by_driver",
    } as Ride);
    expect(cancelled.status).toBe("cancelled_by_driver");
    expect(
      mergeRide(cancelled, { ...base, status: "in_progress" } as Ride).status,
    ).toBe("cancelled_by_driver");
    expect(mergeRide(undefined, base)).toBe(base);
  });
});
