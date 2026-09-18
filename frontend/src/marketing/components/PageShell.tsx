import type { ReactNode } from 'react';

/**
 * PageShell — centered, max-width container for all marketing pages.
 * Max-width: 1120px. Padding: 24px mobile, 48px desktop.
 */
export function PageShell({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`m-page-shell ${className}`.trim()}>
      {children}
    </div>
  );
}
