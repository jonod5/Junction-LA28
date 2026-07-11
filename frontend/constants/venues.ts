export interface VenueStub {
  id: number;
  name: string;
  sport_use: string;
  address: string;
  lat: number;
  lng: number;
}

export const VENUES: VenueStub[] = [
  {
    id: 1,
    name: 'LA Memorial Coliseum',
    sport_use: 'Opening/Closing Ceremony, Athletics',
    address: '3911 S Figueroa St, Los Angeles, CA 90037',
    lat: 34.0141,
    lng: -118.2879,
  },
  {
    id: 2,
    name: 'SoFi Stadium',
    sport_use: 'Football',
    address: '1001 Stadium Dr, Inglewood, CA 90301',
    lat: 33.9535,
    lng: -118.3392,
  },
  {
    id: 3,
    name: 'Dodger Stadium',
    sport_use: 'Baseball',
    address: '1000 Vin Scully Ave, Los Angeles, CA 90012',
    lat: 34.0739,
    lng: -118.24,
  },
  {
    id: 4,
    name: 'Crypto.com Arena',
    sport_use: 'Basketball, Boxing',
    address: '1111 S Figueroa St, Los Angeles, CA 90015',
    lat: 34.043,
    lng: -118.2673,
  },
  {
    id: 5,
    name: 'Peacock Theater',
    sport_use: 'Gymnastics',
    address: '777 Chick Hearn Ct, Los Angeles, CA 90015',
    lat: 34.0448,
    lng: -118.2666,
  },
  {
    id: 6,
    name: 'Rose Bowl Stadium',
    sport_use: 'Football (Soccer)',
    address: '1001 Rose Bowl Dr, Pasadena, CA 91103',
    lat: 34.1613,
    lng: -118.1676,
  },
];
