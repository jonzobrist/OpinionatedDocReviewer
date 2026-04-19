'use client';

import React, { useEffect, useRef, useState } from 'react';

export function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chartIdRef = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const run = async () => {
      const target = containerRef.current;
      if (!target) return;
      try {
        const mod = await import('mermaid');
        const mermaid = mod.default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'neutral',
          suppressErrorRendering: true
        });
        const result = await mermaid.render(chartIdRef.current, chart);
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = result.svg;
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Mermaid rendering failed');
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <div className="mermaid-fallback">
        Mermaid render error: {error}
        <pre>{chart}</pre>
      </div>
    );
  }

  return <div className="mermaid-diagram" ref={containerRef} />;
}

export default MermaidDiagram;
