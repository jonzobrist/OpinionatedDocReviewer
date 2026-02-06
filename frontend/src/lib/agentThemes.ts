export type AgentTheme = {
  color: string;
  label?: string;
};

const STORAGE_KEY = 'odr_agent_themes';

export function loadAgentThemes(): Record<string, AgentTheme> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, AgentTheme>;
  } catch {
    return {};
  }
}

export function saveAgentThemes(themes: Record<string, AgentTheme>) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(themes));
}

export function getThemeForPersona(
  themes: Record<string, AgentTheme>,
  personaId: number,
  fallback: string
) {
  const theme = themes[String(personaId)];
  return theme?.color ?? fallback;
}
