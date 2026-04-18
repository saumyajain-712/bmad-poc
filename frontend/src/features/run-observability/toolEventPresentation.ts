const SECRET_PATTERNS: RegExp[] = [
  /sk-[a-zA-Z0-9]{20,}/g,
  /Bearer\s+[a-zA-Z0-9._-]+/gi,
  /(?:password|passwd|pwd)\s*[:=]\s*\S+/gi,
  /(?:api[_-]?key|apikey|secret)\s*[:=]\s*\S+/gi,
];

export function redactSensitivePatterns(text: string): string {
  let out = text;
  for (const re of SECRET_PATTERNS) {
    out = out.replace(re, '[redacted]');
  }
  return out;
}

function payloadToString(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value ?? {}, (_key, v) => (typeof v === 'bigint' ? v.toString() : v));
  } catch {
    return '[unserializable]';
  }
}

export function summarizeToolPayload(value: unknown, maxLen = 120): string {
  const raw = payloadToString(value);
  const compact = raw.replace(/\s+/g, ' ').trim();
  const truncated =
    compact.length > maxLen ? `${compact.slice(0, maxLen - 3).trimEnd()}...` : compact;
  return redactSensitivePatterns(truncated);
}
