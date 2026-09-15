export function CalculationStepper({ calculation }: { calculation: string[] }) {
  if (!calculation.length) return null;
  return <ol className="calculation-stepper" aria-label="How this decision was calculated">{calculation.slice(0, 4).map((step, index) => <li key={`${index}-${step}`}><span>{index + 1}</span>{step}</li>)}</ol>;
}
