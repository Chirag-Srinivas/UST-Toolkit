import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { AnalyticsBundle, QueueSample } from "../types";
import { cssColors } from "../theme";
import { EChart } from "../components/EChart";
import { Metric } from "../components/Metric";

interface OperationsViewProps {
  data: AnalyticsBundle;
}

function percentile(values: number[], fraction: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.min(sorted.length - 1, Math.floor(fraction * sorted.length))];
}

export function OperationsView({ data }: OperationsViewProps) {
  const dispatchPeak = Math.max(...data.queueSeries.map((row) => row.uamDispatch), 0);
  const waits = data.waitTimes.map((item) => item.waitSeconds);
  const p95Wait = percentile(waits, 0.95);
  const peakCapacity = useMemo(() => {
    let peak = {
      utilisation: 0,
      movementsLastHour: 0,
      capacityVehPerHour: 0,
      facilityName: "No observed movements",
    };
    for (const facility of data.capacity.byVertiport) {
      for (const sample of facility.series) {
        if (sample.utilisation > peak.utilisation) {
          peak = {
            utilisation: sample.utilisation,
            movementsLastHour: sample.movementsLastHour,
            capacityVehPerHour: sample.capacityVehPerHour,
            facilityName: facility.name,
          };
        }
      }
    }
    return peak;
  }, [data.capacity.byVertiport]);
  const movementBreakdown = data.capacity.byVertiport
    .map((facility) => `${facility.name}: ${facility.movementCount}`)
    .join(" · ");
  const constraintWarning =
    data.capacity.breachProportion > 0 ||
    data.capacity.headwayViolationCount > 0;
  const passengerStages = useMemo(
    () => data.queueStages.filter((stage) => stage.key !== "fatoOccupancy"),
    [data.queueStages],
  );

  const queueOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [
        cssColors.terminal,
        cssColors.dispatch,
        cssColors.boarding,
      ],
      grid: { left: 55, right: 22, top: 42, bottom: 50 },
      legend: {
        top: 2,
        textStyle: { color: cssColors.textMuted },
      },
      tooltip: { trigger: "axis" },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 6 }],
      xAxis: {
        type: "value",
        name: "Simulation time",
        min: data.run.startTime,
        max: data.run.endTime,
        nameTextStyle: { color: cssColors.textMuted },
        axisLabel: {
          color: cssColors.textMuted,
          formatter: (value: number) =>
            `${String(Math.floor(value / 3600)).padStart(2, "0")}:${String(
              Math.floor((value % 3600) / 60),
            ).padStart(2, "0")}`,
        },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      yAxis: {
        type: "value",
        name: "Passengers",
        nameTextStyle: { color: cssColors.textMuted },
        axisLabel: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      series: passengerStages.map((stage) => ({
        name: stage.label,
        type: "line",
        step: "end",
        showSymbol: false,
        lineStyle: { width: 2 },
        areaStyle:
          stage.key === "uamDispatch" ? { opacity: 0.08 } : undefined,
        data: data.queueSeries.map((sample) => [
          sample.time,
          sample[stage.key as keyof QueueSample],
        ]),
      })),
    }),
    [data, passengerStages],
  );

  const fatoOccupancyOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [cssColors.fato, cssColors.dispatch, cssColors.terminal],
      grid: { left: 55, right: 22, top: 42, bottom: 50 },
      legend: {
        top: 2,
        textStyle: { color: cssColors.textMuted },
      },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => `${Number(value)} aircraft`,
      },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 6 }],
      xAxis: {
        type: "value",
        name: "Simulation time",
        min: data.run.startTime,
        max: data.run.endTime,
        nameTextStyle: { color: cssColors.textMuted },
        axisLabel: {
          color: cssColors.textMuted,
          formatter: (value: number) =>
            `${String(Math.floor(value / 3600)).padStart(2, "0")}:${String(
              Math.floor((value % 3600) / 60),
            ).padStart(2, "0")}`,
        },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      yAxis: {
        type: "value",
        name: "Aircraft",
        min: 0,
        minInterval: 1,
        nameTextStyle: { color: cssColors.textMuted },
        axisLabel: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      series: data.fatoOccupancyByVertiport.map((facility) => ({
        name: facility.name,
        type: "line" as const,
        step: "end" as const,
        showSymbol: false,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.08 },
        data: facility.series.map((sample) => [sample.time, sample.occupancy]),
      })),
    }),
    [data],
  );

  const capacityOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [cssColors.air, cssColors.dispatch, cssColors.terminal],
      grid: { left: 55, right: 22, top: 24, bottom: 46 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => `${Math.round(Number(value) * 100)}%`,
      },
      xAxis: {
        type: "value",
        min: data.run.startTime,
        max: data.run.endTime,
        axisLabel: {
          color: cssColors.textMuted,
          formatter: (value: number) =>
            `${String(Math.floor(value / 3600)).padStart(2, "0")}:${String(
              Math.floor((value % 3600) / 60),
            ).padStart(2, "0")}`,
        },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      yAxis: {
        type: "value",
        name: "FATO utilisation",
        min: 0,
        axisLabel: {
          color: cssColors.textMuted,
          formatter: (value: number) => `${Math.round(value * 100)}%`,
        },
        nameTextStyle: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      legend: {
        top: 0,
        textStyle: { color: cssColors.textMuted },
      },
      series: [
        ...data.capacity.byVertiport.map((facility) => ({
          type: "line" as const,
          name: facility.name,
          showSymbol: false,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.12 },
          data: facility.series.map((sample) => [
            sample.time,
            sample.utilisation,
          ]),
        })),
        {
          type: "line",
          name: "Design capacity",
          showSymbol: false,
          lineStyle: { opacity: 0 },
          data: [
            [data.run.startTime, 1],
            [data.run.endTime, 1],
          ],
          markLine: {
            symbol: "none",
            lineStyle: { color: cssColors.destructive, type: "dashed", width: 1.5 },
            label: {
              formatter: "Design capacity",
              color: cssColors.destructive,
            },
            data: [{ yAxis: 1 }],
          },
        },
      ],
    }),
    [data],
  );

  const waitOption = useMemo<EChartsOption>(() => {
    const buckets = Array.from({ length: 7 }, (_, index) => ({
      lower: index * 60,
      upper: (index + 1) * 60,
      count: 0,
    }));
    for (const wait of data.waitTimes) {
      const index = Math.min(buckets.length - 1, Math.floor(wait.waitSeconds / 60));
      buckets[index].count += 1;
    }
    return {
      animation: false,
      color: [cssColors.dispatch],
      grid: { left: 48, right: 18, top: 18, bottom: 42 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        name: "Pickup wait",
        data: buckets.map((bucket, index) =>
          index === buckets.length - 1
            ? `${bucket.lower / 60}+m`
            : `${bucket.lower / 60}–${bucket.upper / 60}m`,
        ),
        axisLabel: { color: cssColors.textMuted },
        nameTextStyle: { color: cssColors.textMuted },
      },
      yAxis: {
        type: "value",
        name: "Passengers",
        minInterval: 1,
        axisLabel: { color: cssColors.textMuted },
        nameTextStyle: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      series: [{ type: "bar", data: buckets.map((bucket) => bucket.count), barMaxWidth: 42 }],
    };
  }, [data.waitTimes]);

  return (
    <section className="view">
      <header className="view-heading">
        <div>
          <span className="eyebrow">Observed operations</span>
          <h1>Queues, waits and capacity</h1>
        </div>
      </header>

      <div className="metric-row metric-row--four">
        <Metric
          label="Peak dispatch queue"
          value={`${dispatchPeak}`}
          context="passengers awaiting pickup"
        />
        <Metric
          label="95th percentile pickup wait"
          value={`${(p95Wait / 60).toFixed(1)} min`}
          context={`${data.waitTimes.length} observed requests`}
        />
        <Metric
          label="Peak FATO utilisation"
          value={`${(peakCapacity.utilisation * 100).toFixed(1)}%`}
          context={`${peakCapacity.facilityName}: ${peakCapacity.movementsLastHour}/${peakCapacity.capacityVehPerHour} movements in the rolling hour`}
        />
        <Metric
          label="Observed FATO movements"
          value={`${data.capacity.movementCount}`}
          context={movementBreakdown || "take-offs and landings across all vertiports"}
        />
      </div>

      <div className="section-heading">
        <div>
          <span className="eyebrow">Passenger flow · all vertiports combined</span>
          <h2>Processing, dispatch and departure hold</h2>
          <p className="heading-description">
            A pickup moves passengers from the dispatch queue into the departure
            hold. When their aircraft enters traffic, they leave the hold while
            the dispatch queue remains unchanged.
          </p>
        </div>
      </div>
      <EChart
        option={queueOption}
        height={390}
        label="Passenger processing, dispatch queue and departure hold over simulation time"
      />
      <div className="definition-grid definition-grid--three">
        {passengerStages.map((stage) => (
          <div key={String(stage.key)}>
            <strong>{stage.label}</strong>
            <p>{stage.definition}</p>
          </div>
        ))}
      </div>

      <div className="split-grid split-grid--equal">
        <div>
          <div className="section-heading section-heading--compact">
            <div>
              <span className="eyebrow">Aircraft resource · by vertiport</span>
              <h2>FATO occupancy</h2>
              <p className="heading-description">
                Aircraft using or waiting within each airport's take-off or landing
                FATO sequence.
              </p>
            </div>
          </div>
          <EChart
            option={fatoOccupancyOption}
            height={330}
            label="FATO aircraft occupancy by vertiport over simulation time"
          />
        </div>
        <div>
          <div className="section-heading section-heading--compact">
            <div>
              <span className="eyebrow">Capacity pressure · by vertiport</span>
              <h2>FATO capacity utilisation</h2>
              <p className="heading-description">
                Rolling one-hour movements as a share of the enforced design limit.
              </p>
            </div>
          </div>
          <EChart
            option={capacityOption}
            height={330}
            label="Rolling FATO movement utilisation against design capacity"
          />
        </div>
      </div>
      <p
        className={`status-note${constraintWarning ? "" : " status-note--success"}`}
      >
        <strong>
          {constraintWarning
            ? "Constraint validation warning."
            : "Enforced FATO constraints validated."}
        </strong>{" "}
        {constraintWarning
          ? `${(data.capacity.breachProportion * 100).toFixed(1)}% capacity-breach time and ${data.capacity.headwayViolationCount}/${data.capacity.headwayComparisonCount} headway violations were detected.`
          : "No rolling-capacity or minimum-separation violations were detected. These checks are retained as diagnostics rather than performance KPIs."}
      </p>

      <div className="section-heading">
        <div>
          <span className="eyebrow">Passenger experience</span>
          <h2>UAM pickup wait distribution</h2>
        </div>
      </div>
      <EChart
        option={waitOption}
        height={330}
        label="Distribution of passenger UAM pickup waiting times"
      />

    </section>
  );
}
