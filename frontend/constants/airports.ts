export interface AirportStub {
  kind: 'airport';
  code: string;
  name: string;
  terminal_info: string;
  lat: number;
  lng: number;
}

export const AIRPORTS: AirportStub[] = [
  {
    kind: 'airport',
    code: 'LAX',
    name: 'Los Angeles International Airport',
    terminal_info: 'Terminals 1–8 + Tom Bradley International',
    lat: 33.9425,
    lng: -118.4081,
  },
  {
    kind: 'airport',
    code: 'BUR',
    name: 'Hollywood Burbank Airport',
    terminal_info: 'Single terminal',
    lat: 34.2007,
    lng: -118.3585,
  },
  {
    kind: 'airport',
    code: 'LGB',
    name: 'Long Beach Airport',
    terminal_info: 'Terminal A',
    lat: 33.8179,
    lng: -118.1444,
  },
  {
    kind: 'airport',
    code: 'ONT',
    name: 'Ontario International Airport',
    terminal_info: 'Terminals 2 & 4',
    lat: 34.056,
    lng: -117.6009,
  },
  {
    kind: 'airport',
    code: 'VNY',
    name: 'Van Nuys Airport',
    terminal_info: 'Private & charter aviation',
    lat: 34.2098,
    lng: -118.4901,
  },
];
