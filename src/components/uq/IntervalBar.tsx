
interface IntervalBarProps {
  value: number;
  lower: number | null;
  upper: number | null;
  minVal?: number;
  maxVal?: number;
  units?: string;
}

export function IntervalBar({
  value,
  lower,
  upper,
  minVal = 0,
  maxVal = 10,
  units = '',
}: IntervalBarProps) {
  // If no bounds are provided, just show the point estimate text
  if (lower === null || upper === null) {
    return (
      <span className="font-mono text-slate-100 font-medium">
        {value.toFixed(2)}
        {units && <span className="text-slate-500 text-[10px] ml-0.5">{units}</span>}
      </span>
    );
  }

  // Calculate percentage positions for the SVG visualization
  const span = maxVal - minVal;
  const toPercent = (val: number) => {
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    return ((clamped - minVal) / (span || 1)) * 100;
  };

  const valPos = toPercent(value);
  const lowerPos = toPercent(lower);
  const upperPos = toPercent(upper);

  return (
    <div className="flex flex-col gap-1 w-full max-w-[120px] select-none">
      <div className="flex items-baseline justify-between text-[10px]">
        <span className="font-mono text-slate-100 font-semibold">{value.toFixed(2)}</span>
        <span className="font-mono text-slate-500 text-[9px]">
          [{lower.toFixed(1)}–{upper.toFixed(1)}]
        </span>
      </div>
      
      {/* Visual representation */}
      <div className="relative w-full h-2.5 flex items-center bg-slate-800/60 dark:bg-slate-900/40 border border-slate-700/30 rounded-full overflow-hidden">
        {/* Interval range line */}
        <div
          className="absolute h-1 bg-brand-500/65 dark:bg-brand-400/65 rounded-full"
          style={{
            left: `${Math.min(lowerPos, upperPos)}%`,
            width: `${Math.abs(upperPos - lowerPos)}%`,
          }}
        />
        {/* Point estimate dot */}
        <div
          className="absolute w-2 h-2 bg-slate-100 border border-brand-600 dark:border-brand-400 rounded-full shadow-sm"
          style={{
            left: `${valPos}%`,
            transform: 'translateX(-50%)',
          }}
        />
      </div>
    </div>
  );
}
