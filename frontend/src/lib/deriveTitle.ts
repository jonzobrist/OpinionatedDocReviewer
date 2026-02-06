export function deriveTitle(filename: string, content: string) {
  const cleaned = filename.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim();
  if (cleaned.length > 0) return cleaned;
  return 'Untitled document';
}
