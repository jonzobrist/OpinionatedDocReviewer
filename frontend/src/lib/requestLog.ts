type HeaderReader = {
  get(name: string): string | null;
};

function normalizeHeaderValue(value: string | null): string {
  const trimmed = (value ?? '').trim();
  return trimmed || '-';
}

export function summarizeForwardedHeaders(headers: HeaderReader): {
  xForwardedFor: string;
  xRealIp: string;
} {
  return {
    xForwardedFor: normalizeHeaderValue(headers.get('x-forwarded-for')),
    xRealIp: normalizeHeaderValue(headers.get('x-real-ip'))
  };
}
