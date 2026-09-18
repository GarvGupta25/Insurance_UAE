import type { ReactNode } from 'react';

/**
 * Section — consistent vertical rhythm for marketing page blocks.
 * 40px top/bottom padding on mobile, 64px on desktop.
 * Use `tinted` to apply the alternating surface-tint background.
 */
export function Section({
  children,
  tinted = false,
  className = '',
  id,
}: {
  children: ReactNode;
  tinted?: boolean;
  className?: string;
  id?: string;
}) {
  const classes = [
    'm-section',
    tinted ? 'm-section--tinted' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <section className={classes} id={id}>
      {children}
    </section>
  );
}
