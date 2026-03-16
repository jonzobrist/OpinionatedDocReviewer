import { PersonaRead } from './types';

export type AgentListSort = 'order' | 'name' | 'status';

function compareByOrder(a: PersonaRead, b: PersonaRead): number {
  return a.sort_order - b.sort_order || a.id - b.id;
}

function compareByName(a: PersonaRead, b: PersonaRead): number {
  const byName = a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  if (byName !== 0) return byName;
  return compareByOrder(a, b);
}

function compareByStatus(a: PersonaRead, b: PersonaRead): number {
  if (a.is_active !== b.is_active) {
    return a.is_active ? -1 : 1;
  }
  return compareByOrder(a, b);
}

function matchesSearch(persona: PersonaRead, search: string): boolean {
  if (!search) return true;
  const haystack = [
    persona.name,
    persona.description ?? '',
    persona.tone ?? '',
    persona.reference_notes ?? '',
    ...persona.focus_areas
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(search);
}

export function listVisibleAgents(
  personas: PersonaRead[],
  searchTerm: string,
  sortBy: AgentListSort
): PersonaRead[] {
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filtered = personas.filter((persona) => matchesSearch(persona, normalizedSearch));
  const sorted = filtered.slice();
  if (sortBy === 'name') {
    sorted.sort(compareByName);
    return sorted;
  }
  if (sortBy === 'status') {
    sorted.sort(compareByStatus);
    return sorted;
  }
  sorted.sort(compareByOrder);
  return sorted;
}

export function createDuplicateAgentName(personas: PersonaRead[], sourceName: string): string {
  const existing = new Set(personas.map((persona) => persona.name.toLowerCase()));
  const base = `${sourceName} Copy`;
  if (!existing.has(base.toLowerCase())) {
    return base;
  }
  let suffix = 2;
  while (existing.has(`${base} ${suffix}`.toLowerCase())) {
    suffix += 1;
  }
  return `${base} ${suffix}`;
}
