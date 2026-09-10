interface MetricProps {
  label: string;
  value: string;
  context?: string;
  tone?: "neutral" | "success" | "warning";
}

export function Metric({
  label,
  value,
  context,
  tone = "neutral",
}: MetricProps) {
  return (
    <div className={`metric metric--${tone}`}>
      <span className="metric__label">{label}</span>
      <strong className="metric__value">{value}</strong>
      {context ? <span className="metric__context">{context}</span> : null}
    </div>
  );
}
