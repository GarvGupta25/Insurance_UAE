import type { ReactNode } from 'react';

export function FormActions({ primaryLabel, onPrimary, primaryDisabled, secondaryLabel, onSecondary }: { primaryLabel: ReactNode; onPrimary: () => void; primaryDisabled?: boolean; secondaryLabel?: ReactNode; onSecondary?: () => void }) {
  return <div className="form-actions"><div>{secondaryLabel && <button type="button" className="quiet" onClick={onSecondary}>{secondaryLabel}</button>}</div><button type="button" disabled={primaryDisabled} onClick={onPrimary}>{primaryLabel}</button></div>;
}
