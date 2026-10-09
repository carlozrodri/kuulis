import type { MapStyleElement } from 'react-native-maps';

/**
 * Google Maps styles in the Verde Ávila palette (Android; iOS uses Apple Maps, which only follows
 * light/dark). Business POIs and transit are muted so the ride (route, pins, moto) stands out.
 */
const base = (c: {
  land: string;
  park: string;
  water: string;
  road: string;
  roadStroke: string;
  arterial: string;
  highway: string;
  highwayStroke: string;
  label: string;
  labelStroke: string;
  building: string;
}): MapStyleElement[] => [
  { elementType: 'geometry', stylers: [{ color: c.land }] },
  { elementType: 'labels.icon', stylers: [{ saturation: -80 }, { lightness: 10 }] },
  { elementType: 'labels.text.fill', stylers: [{ color: c.label }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: c.labelStroke }] },
  { featureType: 'administrative.land_parcel', stylers: [{ visibility: 'off' }] },
  { featureType: 'landscape.man_made', elementType: 'geometry', stylers: [{ color: c.building }] },
  { featureType: 'poi', elementType: 'geometry', stylers: [{ color: c.land }] },
  { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
  { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: c.park }] },
  { featureType: 'poi.park', elementType: 'labels.text', stylers: [{ visibility: 'simplified' }] },
  { featureType: 'road', elementType: 'geometry.fill', stylers: [{ color: c.road }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: c.roadStroke }] },
  { featureType: 'road.arterial', elementType: 'geometry.fill', stylers: [{ color: c.arterial }] },
  { featureType: 'road.highway', elementType: 'geometry.fill', stylers: [{ color: c.highway }] },
  { featureType: 'road.highway', elementType: 'geometry.stroke', stylers: [{ color: c.highwayStroke }] },
  { featureType: 'road.local', elementType: 'labels', stylers: [{ visibility: 'simplified' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: c.water }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: c.label }] },
];

export const lightMapStyle = base({
  land: '#EEF3EF',
  park: '#D3E8DA',
  water: '#BCDDE6',
  road: '#FFFFFF',
  roadStroke: '#DCE6E0',
  arterial: '#FFFFFF',
  highway: '#FFE9B0',
  highwayStroke: '#F2D27E',
  label: '#5B6A63',
  labelStroke: '#F3F7F4',
  building: '#E4ECE7',
});

export const darkMapStyle = base({
  land: '#101A15',
  park: '#14271D',
  water: '#0A2027',
  road: '#1F2D26',
  roadStroke: '#16221C',
  arterial: '#26362E',
  highway: '#3A3622',
  highwayStroke: '#2A2716',
  label: '#9AADA4',
  labelStroke: '#0B1310',
  building: '#15211B',
});
