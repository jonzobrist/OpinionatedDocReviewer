import { describe, expect, it } from 'vitest';
import { createDuplicateAgentName, listVisibleAgents } from '../src/lib/agentList';
import { PersonaRead } from '../src/lib/types';

function persona(overrides: Partial<PersonaRead>): PersonaRead {
  return {
    id: 1,
    tenant_id: 'local-dev',
    name: 'Clarity Editor',
    description: 'Improves flow',
    system_prompt: 'Review for clarity',
    focus_areas: ['structure'],
    tone: 'direct',
    reference_notes: null,
    output_requirements: {
      format: 'bullet_list',
      max_bullets: 4,
      require_quote_excerpt: true,
      require_actionable: true,
      include_severity: false
    },
    examples: [],
    is_default: true,
    is_system_locked: true,
    sort_order: 10,
    color_theme: '#1d8a7a',
    group_id: null,
    is_active: true,
    created_at: new Date().toISOString(),
    ...overrides
  };
}

describe('agent list helpers', () => {
  const personas = [
    persona({ id: 1, name: 'Zeta Reviewer', sort_order: 30, is_active: false }),
    persona({ id: 2, name: 'Alpha Reviewer', sort_order: 20, is_active: true }),
    persona({ id: 3, name: 'Beta Reviewer', sort_order: 10, is_active: true, description: 'Security focus' })
  ];

  it('filters by search term and sorts by order', () => {
    const result = listVisibleAgents(personas, 'reviewer', 'order');
    expect(result.map((item) => item.id)).toEqual([3, 2, 1]);
  });

  it('sorts by name', () => {
    const result = listVisibleAgents(personas, '', 'name');
    expect(result.map((item) => item.name)).toEqual(['Alpha Reviewer', 'Beta Reviewer', 'Zeta Reviewer']);
  });

  it('sorts active agents ahead of disabled in status mode', () => {
    const result = listVisibleAgents(personas, '', 'status');
    expect(result.map((item) => item.id)).toEqual([3, 2, 1]);
  });

  it('builds duplicate names without collisions', () => {
    const result = createDuplicateAgentName(personas, 'Alpha Reviewer');
    expect(result).toBe('Alpha Reviewer Copy');
  });

  it('increments duplicate suffix when needed', () => {
    const withExistingCopies = [
      ...personas,
      persona({ id: 10, name: 'Alpha Reviewer Copy' }),
      persona({ id: 11, name: 'Alpha Reviewer Copy 2' })
    ];
    const result = createDuplicateAgentName(withExistingCopies, 'Alpha Reviewer');
    expect(result).toBe('Alpha Reviewer Copy 3');
  });
});
