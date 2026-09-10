import { useEffect, useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import type { MapViewState } from "@deck.gl/core";
import { TripsLayer } from "@deck.gl/geo-layers";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import Map from "react-map-gl/maplibre";
import type { EChartsOption } from "echarts";
import type {
  AnalyticsBundle,
  IterationOption,
  QueueSample,
  Trajectory,
} from "../types";
import { cssColors, palette } from "../theme";
import { EChart } from "../components/EChart";
import { TimeControls } from "../components/TimeControls";

interface JourneyViewProps {
  data: AnalyticsBundle;
  currentTime: number;
  playing: boolean;
  speed: number;
  resetTime: number;
  onTimeChange: (value: number) => void;
  onPlayingChange: (value: boolean) => void;
  onSpeedChange: (value: number) => void;
  iterations: IterationOption[];
  selectedIteration: number | null;
  iterationLoading: boolean;
  onIterationChange: (value: number) => void;
}

function positionAt(
  trajectory: Trajectory,
  currentTime: number,
): [number, number] | null {
  if (
    currentTime < trajectory.startTime ||
    currentTime > trajectory.endTime ||
    trajectory.timestamps.length < 2
  ) {
    return null;
  }
  let low = 0;
  let high = trajectory.timestamps.length - 1;
  while (low < high - 1) {
    const middle = Math.floor((low + high) / 2);
    if (trajectory.timestamps[middle] <= currentTime) low = middle;
    else high = middle;
  }
  const startTime = trajectory.timestamps[low];
  const endTime = trajectory.timestamps[high];
  const fraction =
    endTime === startTime ? 0 : (currentTime - startTime) / (endTime - startTime);
  const start = trajectory.path[low];
  const end = trajectory.path[high];
  return [
    start[0] + (end[0] - start[0]) * fraction,
    start[1] + (end[1] - start[1]) * fraction,
  ];
}

type ActiveVehicle = {
  id: string;
  vehicleId: string;
  mode: Trajectory["mode"];
  isBackground: boolean;
  position: [number, number];
  passengerCount: number;
  passengerIds: string[];
};

function occupancyAt(
  trajectory: Trajectory,
  currentTime: number,
): { count: number; passengerIds: string[] } {
  let current = { count: 0, passengerIds: [] as string[] };
  for (const sample of trajectory.occupancy ?? []) {
    if (sample.time > currentTime) break;
    current = { count: sample.count, passengerIds: sample.passengerIds };
  }
  return current;
}

function activeVehicles(
  trajectories: Trajectory[],
  currentTime: number,
): ActiveVehicle[] {
  return trajectories
    .map((trajectory) => {
      const position = positionAt(trajectory, currentTime);
      if (!position) return null;
      const occupancy = occupancyAt(trajectory, currentTime);
      return {
        id: trajectory.id,
        vehicleId: trajectory.vehicleId,
        mode: trajectory.mode,
        isBackground: trajectory.isBackground,
        position,
        passengerCount: occupancy.count,
        passengerIds: occupancy.passengerIds,
      };
    })
    .filter((item): item is ActiveVehicle => item !== null);
}

function uniqueRoutes(trajectories: Trajectory[]): Trajectory[] {
  const seen = new Set<string>();
  return trajectories.filter((trajectory) => {
    const first = trajectory.path[0];
    const last = trajectory.path[trajectory.path.length - 1];
    const key = `${trajectory.mode}:${first?.join(",")}:${last?.join(",")}:${trajectory.path.length}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function vehicleColor(mode: Trajectory["mode"]): [number, number, number] {
  if (mode === "walk") return palette.walk;
  if (mode === "bus") return palette.bus;
  if (mode === "train") return palette.train;
  if (mode === "uam") return palette.air;
  if (mode === "car") return palette.car;
  return palette.pt;
}

function vehicleLabel(mode: Trajectory["mode"]): string {
  if (mode === "walk") return "Walking agent";
  if (mode === "uam") return "eVTOL";
  if (mode === "train") return "Train";
  if (mode === "bus") return "Bus";
  if (mode === "car") return "Car";
  return "Transit";
}

export function JourneyView({
  data,
  currentTime,
  playing,
  speed,
  resetTime,
  onTimeChange,
  onPlayingChange,
  onSpeedChange,
  iterations,
  selectedIteration,
  iterationLoading,
  onIterationChange,
}: JourneyViewProps) {
  const walkTrips = useMemo(
    () => data.trajectories.filter((trajectory) => trajectory.mode === "walk"),
    [data.trajectories],
  );
  const carTrips = useMemo(
    () =>
      data.trajectories.filter(
        (trajectory) => trajectory.mode === "car" && !trajectory.isBackground,
      ),
    [data.trajectories],
  );
  const backgroundCarTrips = useMemo(
    () =>
      data.trajectories.filter(
        (trajectory) => trajectory.mode === "car" && trajectory.isBackground,
      ),
    [data.trajectories],
  );
  const busTrips = useMemo(
    () => data.trajectories.filter((trajectory) => trajectory.mode === "bus"),
    [data.trajectories],
  );
  const trainTrips = useMemo(
    () => data.trajectories.filter((trajectory) => trajectory.mode === "train"),
    [data.trajectories],
  );
  const legacyPtTrips = useMemo(
    () => data.trajectories.filter((trajectory) => trajectory.mode === "pt"),
    [data.trajectories],
  );
  const airTrips = useMemo(
    () => data.trajectories.filter((trajectory) => trajectory.mode === "uam"),
    [data.trajectories],
  );
  const busRoutes = useMemo(() => uniqueRoutes(busTrips), [busTrips]);
  const trainRoutes = useMemo(() => uniqueRoutes(trainTrips), [trainTrips]);
  const activeWalk = useMemo(
    () => activeVehicles(walkTrips, currentTime),
    [walkTrips, currentTime],
  );
  const activeCar = useMemo(
    () => activeVehicles(carTrips, currentTime),
    [carTrips, currentTime],
  );
  const activeBackgroundCar = useMemo(
    () => activeVehicles(backgroundCarTrips, currentTime),
    [backgroundCarTrips, currentTime],
  );
  const activeBus = useMemo(
    () => activeVehicles(busTrips, currentTime),
    [busTrips, currentTime],
  );
  const activeTrain = useMemo(
    () => activeVehicles(trainTrips, currentTime),
    [trainTrips, currentTime],
  );
  const activeLegacyPt = useMemo(
    () => activeVehicles(legacyPtTrips, currentTime),
    [legacyPtTrips, currentTime],
  );
  const activeAir = useMemo(
    () => activeVehicles(airTrips, currentTime),
    [airTrips, currentTime],
  );
  const occupiedVehicles = useMemo(
    () =>
      [...activeBus, ...activeTrain, ...activeLegacyPt, ...activeAir].filter(
        (vehicle) => vehicle.passengerCount > 0,
      ),
    [activeBus, activeTrain, activeLegacyPt, activeAir],
  );
  const onboardTotal = occupiedVehicles.reduce(
    (total, vehicle) => total + vehicle.passengerCount,
    0,
  );

  const layers = [
    new PathLayer<Trajectory>({
      id: "bus-route-backgrounds",
      data: busRoutes,
      getPath: (item) => item.path,
      getColor: [...palette.bus, 52],
      widthUnits: "pixels",
      getWidth: 7,
      widthMinPixels: 7,
      capRounded: true,
      jointRounded: true,
    }),
    new PathLayer<Trajectory>({
      id: "train-route-backgrounds",
      data: trainRoutes,
      getPath: (item) => item.path,
      getColor: [...palette.train, 58],
      widthUnits: "pixels",
      getWidth: 10,
      widthMinPixels: 10,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "walk-trails",
      data: walkTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.walk,
      currentTime,
      trailLength: 90,
      fadeTrail: true,
      widthMinPixels: 2,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "background-car-trails",
      data: backgroundCarTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.backgroundTraffic,
      currentTime,
      trailLength: 120,
      fadeTrail: true,
      opacity: 0.42,
      widthMinPixels: 1,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "main-car-trails",
      data: carTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.car,
      currentTime,
      trailLength: 160,
      fadeTrail: true,
      widthMinPixels: 2,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "bus-trails",
      data: busTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.bus,
      currentTime,
      trailLength: 240,
      fadeTrail: true,
      widthMinPixels: 3,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "train-trails",
      data: trainTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.train,
      currentTime,
      trailLength: 300,
      fadeTrail: true,
      widthMinPixels: 4,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "legacy-pt-trails",
      data: legacyPtTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.pt,
      currentTime,
      trailLength: 240,
      fadeTrail: true,
      widthMinPixels: 3,
      capRounded: true,
      jointRounded: true,
    }),
    new TripsLayer<Trajectory>({
      id: "uam-trails",
      data: airTrips,
      getPath: (item) => item.path,
      getTimestamps: (item) => item.timestamps,
      getColor: palette.air,
      currentTime,
      trailLength: 360,
      fadeTrail: true,
      widthMinPixels: 5,
      capRounded: true,
      jointRounded: true,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "walking-agents",
      data: activeWalk,
      getPosition: (item) => item.position,
      getRadius: 32,
      radiusMinPixels: 4,
      radiusMaxPixels: 7,
      getFillColor: [...palette.walk, 245],
      getLineColor: [255, 249, 215, 245],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
    }),
    new TextLayer<ActiveVehicle>({
      id: "walking-agent-symbols",
      data: activeWalk,
      getPosition: (item) => item.position,
      getText: () => "W",
      getColor: [34, 31, 14, 255],
      getSize: 10,
      sizeUnits: "pixels",
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      fontWeight: 800,
      pickable: false,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "onboard-agent-halos",
      data: occupiedVehicles,
      getPosition: (item) => item.position,
      getRadius: (item) => 45 + Math.sqrt(item.passengerCount) * 24,
      radiusMinPixels: 9,
      radiusMaxPixels: 28,
      getFillColor: (item) => [...vehicleColor(item.mode), 38],
      getLineColor: (item) => [...vehicleColor(item.mode), 180],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: false,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "background-car-agents",
      data: activeBackgroundCar,
      getPosition: (item) => item.position,
      getRadius: 25,
      radiusMinPixels: 2,
      radiusMaxPixels: 4,
      getFillColor: [...palette.backgroundTraffic, 175],
      getLineColor: [...palette.backgroundTraffic, 105],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "main-car-agents",
      data: activeCar,
      getPosition: (item) => item.position,
      getRadius: 44,
      radiusMinPixels: 5,
      radiusMaxPixels: 9,
      getFillColor: [...palette.car, 250],
      getLineColor: [232, 255, 242, 250],
      lineWidthMinPixels: 2,
      stroked: true,
      pickable: true,
    }),
    new TextLayer<ActiveVehicle>({
      id: "passenger-car-symbols",
      data: activeCar,
      getPosition: (item) => item.position,
      getText: () => "P",
      getColor: [7, 42, 25, 255],
      getSize: 10,
      sizeUnits: "pixels",
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      fontWeight: 800,
      pickable: false,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "bus-vehicles",
      data: activeBus,
      getPosition: (item) => item.position,
      getRadius: 48,
      radiusMinPixels: 5,
      radiusMaxPixels: 8,
      getFillColor: [...palette.bus, 245],
      getLineColor: [225, 241, 255, 240],
      lineWidthMinPixels: 2,
      stroked: true,
      pickable: true,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "train-vehicles",
      data: activeTrain,
      getPosition: (item) => item.position,
      getRadius: 55,
      radiusMinPixels: 6,
      radiusMaxPixels: 10,
      getFillColor: [...palette.train, 245],
      getLineColor: [242, 232, 255, 240],
      lineWidthMinPixels: 2,
      stroked: true,
      pickable: true,
    }),
    new ScatterplotLayer<ActiveVehicle>({
      id: "legacy-pt-vehicles",
      data: activeLegacyPt,
      getPosition: (item) => item.position,
      getRadius: 48,
      radiusMinPixels: 5,
      radiusMaxPixels: 8,
      getFillColor: [...palette.pt, 240],
      getLineColor: [226, 235, 241, 230],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
    }),
    new TextLayer<ActiveVehicle>({
      id: "surface-transit-symbols",
      data: [...activeBus, ...activeTrain],
      getPosition: (item) => item.position,
      getText: (item) => (item.mode === "train" ? "T" : "B"),
      getColor: [6, 18, 25, 255],
      getSize: 11,
      sizeUnits: "pixels",
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      fontWeight: 800,
      pickable: false,
    }),
    new TextLayer<ActiveVehicle>({
      id: "aircraft",
      data: activeAir,
      getPosition: (item) => item.position,
      getText: () => "EV",
      getColor: [...palette.air, 255],
      getSize: 24,
      sizeUnits: "pixels",
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      pickable: true,
    }),
    new TextLayer<ActiveVehicle>({
      id: "onboard-agent-counts",
      data: occupiedVehicles,
      getPosition: (item) => item.position,
      getText: (item) => String(item.passengerCount),
      getColor: [245, 250, 253, 255],
      getBackgroundColor: [8, 22, 31, 235],
      background: true,
      backgroundPadding: [5, 3],
      getSize: 12,
      sizeUnits: "pixels",
      getPixelOffset: [13, -13],
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      fontWeight: 700,
      pickable: false,
    }),
    new ScatterplotLayer({
      id: "landmark-points",
      data: data.landmarks,
      getPosition: (item) => item.position,
      getRadius: (item) => (item.kind === "vertiport" ? 115 : 85),
      radiusMinPixels: 7,
      radiusMaxPixels: 12,
      getFillColor: (item) =>
        item.kind === "vertiport"
          ? [...palette.air, 220]
          : [...palette.terminal, 220],
      getLineColor: [230, 240, 245, 230],
      lineWidthMinPixels: 1,
      stroked: true,
    }),
    new TextLayer({
      id: "landmark-labels",
      data: data.landmarks,
      getPosition: (item) => item.position,
      getText: (item) => item.label,
      getColor: [228, 238, 244, 255],
      getSize: 13,
      sizeUnits: "pixels",
      getPixelOffset: [0, -17],
      fontWeight: 500,
    }),
  ];

  const queueOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      backgroundColor: "transparent",
      color: [
        cssColors.terminal,
        cssColors.dispatch,
        cssColors.boarding,
        cssColors.fato,
      ],
      grid: { left: 46, right: 18, top: 28, bottom: 34 },
      tooltip: { trigger: "axis", valueFormatter: (value) => `${value}` },
      legend: {
        top: 0,
        textStyle: { color: cssColors.textMuted },
        itemWidth: 16,
      },
      xAxis: {
        type: "value",
        min: data.run.startTime,
        max: data.run.endTime,
        axisLabel: {
          color: cssColors.textMuted,
          formatter: (value: number) => {
            const hours = Math.floor(value / 3600);
            const minutes = Math.floor((value % 3600) / 60);
            return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
          },
        },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      yAxis: {
        type: "value",
        name: "Passengers / aircraft",
        nameTextStyle: { color: cssColors.textMuted },
        axisLabel: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      series: [
        ["Terminal", "terminalProcessing"],
        ["Dispatch", "uamDispatch"],
        ["Awaiting departure", "boardingHold"],
        ["FATO", "fatoOccupancy"],
      ].map(([name, key]) => ({
        name,
        type: "line",
        showSymbol: false,
        step: "end",
        lineStyle: { width: 2 },
        data: data.queueSeries.map((row) => [
          row.time,
          row[key as keyof QueueSample],
        ]),
        markLine:
          name === "Terminal"
            ? {
                symbol: "none",
                silent: true,
                lineStyle: { color: "rgba(230,240,245,.55)", width: 1 },
                label: { show: false },
                data: [{ xAxis: currentTime }],
              }
            : undefined,
      })),
    }),
    [data, currentTime],
  );

  const centerLongitude = (data.bounds.west + data.bounds.east) / 2;
  const centerLatitude = (data.bounds.south + data.bounds.north) / 2;
  const initialViewState = useMemo<MapViewState>(
    () => ({
      longitude: centerLongitude,
      latitude: centerLatitude,
      zoom: 8.8,
      pitch: 38,
      bearing: -8,
    }),
    [centerLongitude, centerLatitude],
  );
  // Playback updates currentTime every animation frame. Keep the camera in
  // separate state so wheel, pinch and drag interactions remain authoritative.
  const [viewState, setViewState] = useState<MapViewState>(initialViewState);
  useEffect(() => setViewState(initialViewState), [initialViewState]);
  const mapStyle =
    import.meta.env.VITE_MAP_STYLE_URL ||
    "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

  return (
    <section className="view">
      <header className="view-heading">
        <div>
          <span className="eyebrow">Observed journey</span>
          <h1>Multimodal journey playback</h1>
        </div>
        <div className="journey-heading-actions">
          <label className="iteration-selector">
            <span>MATSim iteration</span>
            <select
              value={selectedIteration ?? ""}
              disabled={iterationLoading || !iterations.length}
              onChange={(event) => onIterationChange(Number(event.target.value))}
              aria-label="Select MATSim iteration"
            >
              {iterations.map((iteration) => (
                <option key={iteration.number} value={iteration.number}>
                  {iteration.label}
                </option>
              ))}
            </select>
          </label>
          <div className="live-summary" aria-live="polite">
            <span><i className="legend-dot legend-dot--walk" />{activeWalk.length} walking</span>
            <span><i className="legend-dot legend-dot--car" />{activeCar.length} passenger cars</span>
            <span><i className="legend-dot legend-dot--background-traffic" />{activeBackgroundCar.length} background cars</span>
            <span><i className="legend-dot legend-dot--bus" />{activeBus.length} buses</span>
            <span><i className="legend-dot legend-dot--train" />{activeTrain.length} trains</span>
            <span><i className="legend-dot legend-dot--air" />{activeAir.length} eVTOLs</span>
            <span className="occupancy-key">{onboardTotal} agents onboard · map badge shows each vehicle count</span>
          </div>
        </div>
      </header>

      <TimeControls
        time={currentTime}
        startTime={data.run.startTime}
        endTime={data.run.endTime}
        resetTime={resetTime}
        playing={playing}
        speed={speed}
        onTimeChange={onTimeChange}
        onPlayingChange={onPlayingChange}
        onSpeedChange={onSpeedChange}
      />

      <div className="map-frame">
        {iterationLoading ? (
          <div className="map-loading" role="status">
            <div className="spinner" />
            <span>Preparing selected iteration…</span>
          </div>
        ) : null}
        <DeckGL
          viewState={viewState}
          onViewStateChange={({ viewState: nextViewState }) =>
            setViewState(nextViewState as MapViewState)
          }
          controller
          layers={layers}
          getTooltip={({ object }) => {
            const vehicle = object as ActiveVehicle | undefined;
            if (!vehicle || typeof vehicle.passengerCount !== "number") return null;
            if (vehicle.mode === "walk") {
              return { text: `Walking agent ${vehicle.vehicleId}` };
            }
            if (vehicle.isBackground) {
              return { text: `Background car ${vehicle.vehicleId}` };
            }
            if (vehicle.mode === "car") {
              return { text: `Passenger car ${vehicle.vehicleId}` };
            }
            const passengers = vehicle.passengerIds.length
              ? `\nAgents: ${vehicle.passengerIds.join(", ")}`
              : "";
            return {
              text: `${vehicleLabel(vehicle.mode)} ${vehicle.vehicleId}\n${vehicle.passengerCount} agent${vehicle.passengerCount === 1 ? "" : "s"} onboard${passengers}`,
            };
          }}
        >
          <Map mapStyle={mapStyle} attributionControl={{ compact: true }} />
        </DeckGL>
      </div>

      <div className="section-heading">
        <div>
          <span className="eyebrow">Synchronized operations</span>
          <h2>Queues and constrained resources</h2>
        </div>
      </div>
      <EChart
        option={queueOption}
        height={250}
        label="Queue levels synchronized to the journey playback time"
      />
    </section>
  );
}
