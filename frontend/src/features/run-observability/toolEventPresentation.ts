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

export function summarizeToolPayload(value: unknown, maxLen = 120): string {
  const raw =
    typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 0);
  const compact = raw.replace(/\s+/g, ' ').trim();
  const truncated =
    compact.length > maxLen ? `${compact.slice(0, maxLen - 3).trimEnd()}...` : compact;
  return redactSensitivePatterns(truncated);
}
