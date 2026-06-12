interface Props {
  values: number[];
  width?: number;
  height?: number;
  /** Stroke color; defaults to green when rising, red when falling */
  color?: string;
}

export function MiniSparkline({ values, width = 120, height = 28, color }: Props) {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = 2;
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - pad * 2);
  const y = (v: number) => pad + (height - pad * 2) * (1 - (v - min) / (max - min || 1));
  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const rising = values[values.length - 1] >= values[0];
  const stroke = color ?? (rising ? "#34d399" : "#f87171");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block">
      <polyline
        points={line}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={x(values.length - 1)} cy={y(values[values.length - 1])} r={2} fill={stroke} />
    </svg>
  );
}
