import { describe, expect, it } from 'vitest';
import { getThemeForPersona } from '../src/lib/agentThemes';


describe('agent themes', () => {
  it('falls back to default when no theme stored', () => {
    expect(getThemeForPersona({}, 1, '#123')).toBe('#123');
  });

  it('returns stored color for persona', () => {
    const themes = { '2': { color: '#ff0000' } };
    expect(getThemeForPersona(themes, 2, '#123')).toBe('#ff0000');
  });
});
