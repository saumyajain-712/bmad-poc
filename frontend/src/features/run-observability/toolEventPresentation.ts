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

function jsonReplacer(_key: string, v: unknown): unknown {
  return typeof v === 'bigint' ? v.toString() : v;
}

function payloadToString(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value ?? {}, jsonReplacer);
  } catch {
    return '[unserializable]';
  }
}

/**
 * Pretty-print JSON with BigInt-safe serialization and the same redaction rules as summaries (NFR12).
 * Use for full tool_input / tool_output and full-event debug dumps in the detail panel.
 */
export function formatRedactedJsonPretty(value: unknown): string {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value) as unknown;
      const pretty = JSON.stringify(parsed, jsonReplacer, 2) ?? '[unserializable]';
      return redactSensitivePatterns(pretty);
    } catch {
      return redactSensitivePatterns(value);
    }
  }
  try {
    const s = JSON.stringify(value ?? {}, jsonReplacer, 2) ?? '[unserializable]';
    return redactSensitivePatterns(s);
  } catch {
    return '[unserializable]';
  }
}

/** Alias for story wording — full payload display in inspect UI. */
export const formatFullPayloadForDisplay = formatRedactedJsonPretty;

export function summarizeToolPayload(value: unknown, maxLen = 120): string {
  const raw = payloadToString(value);
  const compact = raw.replace(/\s+/g, ' ').trim();
  const truncated =
    compact.length > maxLen ? `${compact.slice(0, maxLen - 3).trimEnd()}...` : compact;
  return redactSensitivePatterns(truncated);
}
