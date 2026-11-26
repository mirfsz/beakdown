export default function TimeScrubber({
  step,
  count,
  onChange,
}: {
  step: number;
  count: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="timeline">
      Inspect execution step{" "}
      <input
        aria-label="Execution step"
        type="range"
        min={0}
        max={count - 1}
        value={step}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span>
        {step + 1} / {count}
      </span>
    </label>
  );
}
