// Coarse geography helpers — we never store precise coordinates.
// Browser geolocation, if granted, is rounded to the nearest 0.5° before persistence.

export function roundCoarse(lat: number, lng: number) {
  const r = (n: number) => Math.round(n * 2) / 2; // 0.5° ≈ 55km — well above neighborhood resolution
  return { lat: r(lat), lng: r(lng) };
}

// Haversine on coarse coordinates returns a coarse distance bucket label.
export function haversineKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(s)));
}

export function distanceBucket(km: number): { label: string; weight: number } {
  // weight is multiplier used by the trade-match scorer (closer == higher).
  if (km < 50) return { label: 'In your city', weight: 1.0 };
  if (km < 200) return { label: 'Same region', weight: 0.85 };
  if (km < 800) return { label: 'Same country', weight: 0.6 };
  if (km < 2500) return { label: 'Same continent', weight: 0.35 };
  return { label: 'International', weight: 0.18 };
}

// Curated region presets keep onboarding privacy-respecting — no geocoding service needed.
export const REGION_PRESETS: { label: string; coords: { lat: number; lng: number } }[] = [
  { label: 'London, UK', coords: { lat: 51.5, lng: -0.0 } },
  { label: 'Manchester, UK', coords: { lat: 53.5, lng: -2.5 } },
  { label: 'Berlin, DE', coords: { lat: 52.5, lng: 13.5 } },
  { label: 'Munich, DE', coords: { lat: 48.0, lng: 11.5 } },
  { label: 'Paris, FR', coords: { lat: 48.5, lng: 2.5 } },
  { label: 'Madrid, ES', coords: { lat: 40.5, lng: -3.5 } },
  { label: 'Barcelona, ES', coords: { lat: 41.5, lng: 2.0 } },
  { label: 'Milan, IT', coords: { lat: 45.5, lng: 9.0 } },
  { label: 'Rome, IT', coords: { lat: 42.0, lng: 12.5 } },
  { label: 'Lisbon, PT', coords: { lat: 38.5, lng: -9.0 } },
  { label: 'Amsterdam, NL', coords: { lat: 52.5, lng: 5.0 } },
  { label: 'Brussels, BE', coords: { lat: 51.0, lng: 4.5 } },
  { label: 'Zurich, CH', coords: { lat: 47.5, lng: 8.5 } },
  { label: 'Vienna, AT', coords: { lat: 48.0, lng: 16.5 } },
  { label: 'Warsaw, PL', coords: { lat: 52.0, lng: 21.0 } },
  { label: 'New York, US', coords: { lat: 40.5, lng: -74.0 } },
  { label: 'Los Angeles, US', coords: { lat: 34.0, lng: -118.0 } },
  { label: 'Chicago, US', coords: { lat: 41.5, lng: -87.5 } },
  { label: 'Toronto, CA', coords: { lat: 43.5, lng: -79.5 } },
  { label: 'Mexico City, MX', coords: { lat: 19.5, lng: -99.0 } },
  { label: 'São Paulo, BR', coords: { lat: -23.5, lng: -46.5 } },
  { label: 'Rio de Janeiro, BR', coords: { lat: -22.5, lng: -43.0 } },
  { label: 'Buenos Aires, AR', coords: { lat: -34.5, lng: -58.5 } },
  { label: 'Bogotá, CO', coords: { lat: 4.5, lng: -74.0 } },
  { label: 'Tokyo, JP', coords: { lat: 35.5, lng: 139.5 } },
  { label: 'Seoul, KR', coords: { lat: 37.5, lng: 127.0 } },
  { label: 'Sydney, AU', coords: { lat: -33.5, lng: 151.0 } },
  { label: 'Cairo, EG', coords: { lat: 30.0, lng: 31.0 } },
  { label: 'Lagos, NG', coords: { lat: 6.5, lng: 3.5 } },
  { label: 'Casablanca, MA', coords: { lat: 33.5, lng: -7.5 } },
];
