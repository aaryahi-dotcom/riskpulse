import type { CSSProperties, ReactNode } from 'react';

export function Blueprint({ style, children, className }: { style?: CSSProperties; children: ReactNode; className?: string }) {
  return (
    <div className={className ? `blueprint ${className}` : 'blueprint'} style={style}>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
      {children}
    </div>
  );
}

export function Muted({ children, pct = 65, style }: { children: ReactNode; pct?: number; style?: CSSProperties }) {
  return <span style={{ color: `color-mix(in srgb, var(--color-text) ${pct}%, transparent)`, ...style }}>{children}</span>;
}
