import { Pause, Play, RotateCcw } from "lucide-react";

interface TimeControlsProps {
  time: number;
  startTime: number;
  endTime: number;
  resetTime: number;
  playing: boolean;
  speed: number;
  onTimeChange: (value: number) => void;
  onPlayingChange: (value: boolean) => void;
  onSpeedChange: (value: number) => void;
}

export function formatClock(totalSeconds: number): string {
  const value = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = value % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

export function TimeControls({
  time,
  startTime,
  endTime,
  resetTime,
  playing,
  speed,
  onTimeChange,
  onPlayingChange,
  onSpeedChange,
}: TimeControlsProps) {
  return (
    <div className="time-controls" aria-label="Simulation playback">
      <button
        className="icon-button icon-button--primary"
        type="button"
        onClick={() => onPlayingChange(!playing)}
        aria-label={playing ? "Pause playback" : "Play simulation"}
      >
        {playing ? <Pause size={17} /> : <Play size={17} />}
      </button>
      <button
        className="icon-button"
        type="button"
        onClick={() => {
          onPlayingChange(false);
          onTimeChange(resetTime);
        }}
        aria-label="Reset to passenger journeys"
      >
        <RotateCcw size={16} />
      </button>
      <strong className="time-controls__clock">{formatClock(time)}</strong>
      <input
        className="time-controls__range"
        type="range"
        min={startTime}
        max={endTime}
        step={1}
        value={Math.min(endTime, Math.max(startTime, time))}
        onChange={(event) => onTimeChange(Number(event.target.value))}
        aria-label="Simulation time"
      />
      <label className="speed-control">
        <span>Speed</span>
        <select
          value={speed}
          onChange={(event) => onSpeedChange(Number(event.target.value))}
        >
          {[1, 5, 10, 20, 60].map((option) => (
            <option key={option} value={option}>
              {option}×
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
