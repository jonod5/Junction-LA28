// Deep links to third-party apps/sites, with trip context prefilled where the
// provider supports it.  We never book or pay — these just hand the traveler
// off to the right app (PRD FR-D1; Uber cost API is deferred, FR-D3).
//
// Everything here is an https URL, not a custom scheme (uber://, bird://):
// on Expo web a custom scheme won't resolve, and the providers' universal
// https links open the app when installed and the site otherwise.

export interface Place {
  lat: number;
  lng: number;
  name?: string;
}

export interface DeepLink {
  provider: string;   // stable key, e.g. "uber"
  label: string;      // button text, e.g. "Open in Uber"
  url: string;
}

/** Uber universal link with pickup + dropoff coordinates and nicknames. */
export function uberLink(origin: Place, destination: Place): DeepLink {
  const p = new URLSearchParams({
    action: 'setPickup',
    'pickup[latitude]': String(origin.lat),
    'pickup[longitude]': String(origin.lng),
    'dropoff[latitude]': String(destination.lat),
    'dropoff[longitude]': String(destination.lng),
  });
  if (origin.name) p.set('pickup[nickname]', origin.name);
  if (destination.name) p.set('dropoff[nickname]', destination.name);
  return { provider: 'uber', label: 'Open in Uber', url: `https://m.uber.com/ul/?${p.toString()}` };
}

/**
 * Waymo One. Waymo exposes no public coordinate deep link, so this opens the
 * app/booking site; the traveler sets the destination there.
 */
export function waymoLink(): DeepLink {
  return { provider: 'waymo', label: 'Open in Waymo', url: 'https://ride.waymo.com/' };
}

/** Bird — opens the app when installed, else the site/store. */
export function birdLink(): DeepLink {
  return { provider: 'bird', label: 'Open Bird', url: 'https://www.bird.co/' };
}

/** Spin. */
export function spinLink(): DeepLink {
  return { provider: 'spin', label: 'Open Spin', url: 'https://www.spin.app/' };
}

/** Metro Bike Share. */
export function metroBikeLink(): DeepLink {
  return { provider: 'metro-bike-share', label: 'Metro Bike Share', url: 'https://bikeshare.metro.net/' };
}

/** Metro TAP fares — how to pay for rail/bus. */
export function metroTapLink(): DeepLink {
  return { provider: 'metro-tap', label: 'Metro TAP fares', url: 'https://www.metro.net/riding/fares/' };
}

// Map a route/vehicle mode to the provider links a traveler would want on it.
// Keys match route_engine mode labels + GBFS provider keys.
const MICRO_PROVIDER_LINKS: Record<string, () => DeepLink> = {
  bird: birdLink,
  spin: spinLink,
  'metro-bike-share': metroBikeLink,
};

/**
 * The deep links relevant to a route option, given its modes.  `providers` is
 * the set of GBFS providers actually used on the option's micromobility legs
 * (so we only show "Open Bird" when a Bird vehicle is part of the plan).
 */
export function linksForModes(
  modes: string[],
  origin: Place,
  destination: Place,
  providers: string[] = [],
): DeepLink[] {
  const links: DeepLink[] = [];
  if (modes.includes('ridehail')) {
    links.push(uberLink(origin, destination), waymoLink());
  }
  if (modes.includes('transit') || modes.includes('metro_micro')) {
    links.push(metroTapLink());
  }
  if (modes.includes('bike') || modes.includes('scooter')) {
    const seen = new Set<string>();
    for (const prov of providers) {
      const make = MICRO_PROVIDER_LINKS[prov];
      if (make && !seen.has(prov)) {
        seen.add(prov);
        links.push(make());
      }
    }
    // If we don't know the specific provider, offer the operators generically.
    if (providers.length === 0) {
      links.push(birdLink(), spinLink(), metroBikeLink());
    }
  }
  return links;
}
