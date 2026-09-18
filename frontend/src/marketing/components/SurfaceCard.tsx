import type { ReactNode } from 'react';

/**
 * SurfaceCard — the single card component for the entire marketing site.
 * White surface, medium border-radius, subtle box-shadow, consistent padding.
 *
 * Reused for: plan cards, guide topic cards, FAQ items, partner cards,
 * "Good to know" callouts, and any card-like block.
 *
 * Do NOT create a second, visually different card component.
 */
export function SurfaceCard({
  children,
  className = '',
  as: Tag = 'div',
  onClick,
}: {
  children: ReactNode;
  className?: string;
  as?: 'div' | 'article' | 'aside';
  onClick?: () => void;
}) {
  return (
    <Tag
      className={`m-surface-card ${className}`.trim()}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
    >
      {children}
    </Tag>
  );
}
