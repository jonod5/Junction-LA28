/**
 * Turns the hand-collected venue prose fields into short, scannable
 * {label, value} rows for the venue detail panel — bold label, terse
 * fragment, one fact per line, instead of a run-on paragraph.
 *
 * This only reformats presentation; it never invents or drops facts (aside
 * from hedge asides that just flag "we don't know X", which the panel
 * already omits by not rendering a row at all).
 */

export interface FactRow {
  label: string;
  value: string;
}

// Parenthetical hedges that flag missing/uncertain detail rather than
// carrying real content, e.g. "(exact opening time before events not
// stated)". Distinct from the API's citation stripping — this is about
// uncertainty language, not sourcing — so a missing value just disappears
// instead of rendering an apology.
const HEDGE_PAREN_RE =
  /\s*\([^()]*\b(?:not stated|not confirmed|unconfirmed|tbd|not given|not specified)\b[^()]*\)/gi;

// "between X and Y" -> "(X–Y)" — the same fact in a third of the words.
const BETWEEN_RE = /\bbetween\s+([^,.;()]+?)\s+and\s+([^,.;()]+?)(?=[.,;)]|$)/gi;

const LEADING_FILLER_RE = /^(?:please note that|note that|it should be noted that|it is worth noting that)\s+/i;

// A trailing "; ''" or '; ""' is a placeholder for "no second value given"
// left over from the source spreadsheet — noise, not content.
const TRAILING_EMPTY_QUOTE_RE = /;\s*['"]{2}\s*$/;

function tidy(text: string): string {
  let t = text;
  t = t.replace(HEDGE_PAREN_RE, '');
  t = t.replace(BETWEEN_RE, (_m, a: string, b: string) => `(${a.trim()}–${b.trim()})`);
  t = t.replace(LEADING_FILLER_RE, '');
  t = t.replace(TRAILING_EMPTY_QUOTE_RE, '');
  t = t.replace(/\s{2,}/g, ' ').replace(/\s+([.,;:])/g, '$1').trim();
  t = t.replace(/[.\s]+$/, '');
  return t;
}

/** One DB field -> one row, under a fixed label we already know from the schema. */
export function factRow(label: string, raw: string | null | undefined): FactRow | null {
  if (!raw) return null;
  const value = tidy(raw);
  return value ? { label, value } : null;
}

const CLAUSE_LABEL_RULES: Array<{ test: RegExp; label: string }> = [
  { test: /\$\s?\d|\bfare\b|\bpass\b/i, label: 'Fare' },
  { test: /\blast (?:train|bus)/i, label: 'Last train' },
  { test: /\benhanced service|service begins|lots? open|gates? open/i, label: 'Event-day timing' },
  { test: /walk time.*bus stop|walk.*from bus stop/i, label: 'Walk from bus stop' },
  { test: /\bwalk time/i, label: 'Walk to station' },
  { test: /\d+\s*(?:minutes?|mins?)\s+from\b/i, label: 'Walk to station' },
  { test: /\bnearest bus stop/i, label: 'Bus stop' },
  { test: /\bbike lane|bike path/i, label: 'Bike lane' },
  { test: /\bmetrolink|\bamtrak/i, label: 'Regional rail' },
  { test: /\bscooter|\bbike share|\bdock\b/i, label: 'Micromobility' },
  { test: /\btraffic|511\b/i, label: 'Traffic updates' },
  { test: /\bline\b/i, label: 'Transit note' },
];

function labelClause(clause: string): string {
  for (const rule of CLAUSE_LABEL_RULES) {
    if (rule.test.test(clause)) return rule.label;
  }
  const firstWords = clause.split(/\s+/).slice(0, 2).join(' ').replace(/[:,.]$/, '');
  return firstWords || 'Note';
}

// Street abbreviations and initials are everywhere in this address-heavy
// dataset ("Vermont Ave.", "W. Martin Luther King Jr. Blvd", "S. Hoover
// St."). A naive split on ". " chops every address into fake sentences, so
// a period only ends a sentence when the word before it isn't one of these.
const ABBREV_WORDS = new Set([
  'ave', 'blvd', 'st', 'dr', 'rd', 'ln', 'pkwy', 'ct', 'pl', 'jr', 'sr', 'mt', 'no', 'ste', 'hwy', 'sq', 'ter',
]);

function splitSentences(text: string): string[] {
  const boundary = /\.\s+(?=[A-Z]|$)/g;
  const out: string[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = boundary.exec(text))) {
    const before = text.slice(lastIndex, m.index);
    const lastWord = before.trim().split(/\s+/).pop() ?? '';
    const bare = lastWord.replace(/[^A-Za-z]/g, '').toLowerCase();
    // Matches both a single initial ("W") and a dotted multi-letter
    // initialism with its internal dots but no trailing one ("L.A" — the
    // trailing dot was already consumed by the boundary match itself).
    // Without this, "L.A. Live Way" reads as ending right after "L.A".
    const isInitial = /^[A-Z](\.[A-Z])*\.?$/.test(lastWord);
    if (!ABBREV_WORDS.has(bare) && !isInitial) {
      out.push(text.slice(lastIndex, m.index));
      lastIndex = boundary.lastIndex;
    }
  }
  out.push(text.slice(lastIndex));
  return out.map((s) => s.trim()).filter(Boolean);
}

function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) => {
    if (w.length > 1 && w === w.toUpperCase()) return w; // preserve acronyms: NFL, ADA, MLK
    return w[0].toUpperCase() + w.slice(1).toLowerCase();
  });
}

// A recurring, recognizable shape across venues: "<duration> after an/the
// event(s) end(s)" buried inside a longer sentence about why access is
// restricted. Worth collapsing on its own since the surrounding sentence is
// almost always just a wordy wrapper around this one number.
const POST_EVENT_DELAY_RE = /(\d+(?:\s*[–-]\s*\d+)?)\s*(minutes?|mins?|hours?|hrs?)\s+after\s+(?:an?\s+|the\s+)?events?\s+ends?/i;

function simplifyIfDelayPhrase(text: string): string {
  const m = text.match(POST_EVENT_DELAY_RE);
  return m ? `${m[1]} ${m[2]} after event ends` : text;
}

/**
 * Splits a prose field into one labeled row per fact. Sentences that
 * already carry their own lead-in — "Walk times: ...", "For larger
 * concert-type events, ..." — keep that as the label and stay whole (their
 * internal semicolons are enumerating items, e.g. two station names, not
 * separate facts). Sentences with no such lead-in are the real run-on
 * offenders and get split on semicolons into one fact per clause, each
 * labeled by keyword. `defaultLabel`, when given, is used for any sentence
 * that has no lead-in of its own — covering both the common case (the
 * field is already one fact, e.g. a rideshare zone description) and venues
 * with a few exception sentences tacked on, which then share the same
 * label rather than getting a meaningless first-two-words fallback.
 */
export function splitFacts(raw: string | null | undefined, defaultLabel?: string): FactRow[] {
  if (!raw) return [];
  const sentences = splitSentences(raw.replace(HEDGE_PAREN_RE, ''));

  const rows: FactRow[] = [];
  sentences.forEach((sentence) => {
    const forEvents = sentence.match(/^For\s+([a-z][a-z\s-]{2,30}?)\s+events,\s*(.+)$/i);
    if (forEvents) {
      const value = tidy(forEvents[2]);
      if (value) rows.push({ label: `${titleCase(forEvents[1])} events`, value });
      return;
    }
    const colon = sentence.match(/^([A-Za-z][A-Za-z /]{2,30}):\s*(.+)$/);
    if (colon) {
      const value = tidy(colon[2]);
      if (value) rows.push({ label: titleCase(colon[1]), value });
      return;
    }
    if (defaultLabel) {
      const value = simplifyIfDelayPhrase(tidy(sentence));
      if (value) rows.push({ label: defaultLabel, value });
      return;
    }
    sentence
      .split(/;\s+/)
      .map((c) => tidy(c))
      .filter(Boolean)
      .forEach((clause) => rows.push({ label: labelClause(clause), value: simplifyIfDelayPhrase(clause) }));
  });
  return rows;
}

/** Splits on a separator while respecting parenthesis nesting depth. */
function splitRespectingParens(text: string, sep: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    else if (ch === sep && depth === 0) {
      parts.push(text.slice(start, i));
      start = i + 1;
    }
  }
  parts.push(text.slice(start));
  return parts.map((p) => p.trim()).filter(Boolean);
}

/**
 * A lot_name field is sometimes one lot ("SoFi Lot 1") and sometimes a
 * dozen names grouped by area ("Exposition Park: Blue Structure, Orange
 * Structure...; USC/adjacent structures: ..."). Flattens to individual
 * lot names so the panel can show a count + expander instead of the raw
 * run-on string.
 */
export function parseLotNames(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const groups = splitRespectingParens(raw, ';');
  const items: string[] = [];
  for (const group of groups) {
    const colonIdx = group.indexOf(':');
    // Only treat text before the colon as a group label (not part of a lot
    // name) when it's short — a real group label, not a sentence with a
    // colon in it.
    const body = colonIdx > -1 && colonIdx < 40 ? group.slice(colonIdx + 1) : group;
    items.push(...splitRespectingParens(body, ','));
  }
  return items;
}

/**
 * bus_lines_serving is usually "Line X (to Destination), Line Y (to
 * Destination), ..." — parsed into short "code → destination" pills. Falls
 * back to an empty array (caller should show the tidied raw text instead)
 * when the field doesn't follow that per-line pattern.
 */
export function parseBusLines(raw: string | null | undefined): Array<{ code: string; detail: string }> {
  if (!raw) return [];
  const out: Array<{ code: string; detail: string }> = [];
  const re = /([^,()]+?)\s*\(([^()]+)\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw))) {
    out.push({ code: shortLineCode(m[1].trim()), detail: m[2].trim().replace(/^to\s+/i, '') });
  }
  return out;
}

function shortLineCode(name: string): string {
  const afterLine = name.match(/\bLine\s+(\w+)/i);
  if (afterLine) return afterLine[1];
  const beforeLine = name.match(/(\w+)\s+Line\b/i);
  if (beforeLine) return beforeLine[1];
  return name;
}
