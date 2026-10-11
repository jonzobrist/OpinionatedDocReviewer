// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MermaidDiagram } from '../app/components/MermaidDiagram';

// jsdom has no SVG layout engine. Only stub measurement; use real Mermaid,
// KaTeX and DOMPurify so dependency upgrades exercise rendering and sanitizing.
beforeEach(() => {
  // Match modern browsers' MathML support detection (absent from jsdom).
  vi.stubGlobal('MathMLElement', Element);
  Object.defineProperty(SVGElement.prototype, 'getBBox', {
    configurable: true,
    value: () => ({ x: 0, y: 0, width: 100, height: 20 })
  });
  Object.defineProperty(SVGElement.prototype, 'getComputedTextLength', {
    configurable: true,
    value: () => 100
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function renderedSvg(container: HTMLElement) {
  return waitFor(() => {
    const svg = container.querySelector('.mermaid-diagram svg');
    expect(svg).toBeTruthy();
    if (!svg) throw new Error('Expected Mermaid SVG');
    return svg;
  }, { timeout: 10_000 });
}

describe('Mermaid dependency compatibility and sanitization', () => {
  it('renders a flowchart with the real renderer', async () => {
    const { container } = render(<MermaidDiagram chart={'graph TD; A[Review] --> B[Approve]'} />);
    const svg = await renderedSvg(container);
    expect(svg.textContent).toContain('Review');
    expect(svg.textContent).toContain('Approve');
    expect(container.querySelector('.mermaid-fallback')).toBeNull();
  });

  it('renders math labels through the patched KaTeX dependency', async () => {
    const { container } = render(<MermaidDiagram chart={'graph TD; A["$$x^2 + 1$$"] --> B[Done]'} />);
    const svg = await renderedSvg(container);
    expect(svg.querySelector('.katex')).toBeTruthy();
    expect(svg.textContent).toContain('Done');
    expect(container.querySelector('.mermaid-fallback')).toBeNull();
  });

  it('removes executable labels and links from untrusted diagram content', async () => {
    const chart = 'graph TD\nA["<b onclick=alert(1)>Review</b><script>alert(2)</script>"] --> B[Approve]\nclick B "javascript:alert(3)"';
    const { container } = render(<MermaidDiagram chart={chart} />);
    const svg = await renderedSvg(container);
    expect(svg.textContent).toContain('Review');
    expect(svg.querySelector('script, [onerror], [onload], [onclick]')).toBeNull();
    for (const element of svg.querySelectorAll('[href], [xlink\\:href], [src]')) {
      for (const attribute of ['href', 'xlink:href', 'src']) {
        expect(element.getAttribute(attribute) ?? '').not.toMatch(/^\s*(javascript|vbscript|data):/i);
      }
    }
  });

  it('shows a readable fallback for invalid Mermaid syntax', async () => {
    const chart = 'this is not a valid diagram';
    render(<MermaidDiagram chart={chart} />);
    expect(await screen.findByText(/Mermaid render error:/)).toBeTruthy();
    expect(screen.getByText(chart)).toBeTruthy();
  });
});
