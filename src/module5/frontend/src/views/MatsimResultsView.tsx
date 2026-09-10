import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { GeneralMatsimResults } from "../types";
import { EChart } from "../components/EChart";
import { Metric } from "../components/Metric";
import { cssColors } from "../theme";

interface MatsimResultsViewProps {
  data: GeneralMatsimResults | null;
  error: string | null;
}

const modeColours = [
  cssColors.terminal,
  cssColors.dispatch,
  cssColors.boarding,
  cssColors.fato,
  "#43c27a",
  "#f46469",
];

function chartBase(): Partial<EChartsOption> {
  return {
    animationDuration: 280,
    backgroundColor: "transparent",
    color: modeColours,
    grid: { left: 58, right: 18, top: 36, bottom: 38 },
    tooltip: { trigger: "axis" },
    legend: {
      top: 0,
      textStyle: { color: cssColors.textMuted },
      itemWidth: 16,
    },
    xAxis: {
      type: "category",
      name: "Iteration",
      nameLocation: "middle",
      nameGap: 26,
      nameTextStyle: { color: cssColors.textMuted },
      axisLabel: { color: cssColors.textMuted },
      axisLine: { lineStyle: { color: cssColors.grid } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: cssColors.textMuted },
      splitLine: { lineStyle: { color: cssColors.grid } },
    },
  };
}

function displayMode(mode: string): string {
  return mode
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function MatsimResultsView({ data, error }: MatsimResultsViewProps) {
  const options = useMemo(() => {
    if (!data) return null;
    const iterations = data.availableIterations.map(String);
    const baseXAxis = () => ({
      ...(chartBase().xAxis as object),
      data: iterations,
    });
    const baseYAxis = () => ({ ...(chartBase().yAxis as object) });

    const scores: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Score",
        nameTextStyle: { color: cssColors.textMuted },
      },
      series: [
        { key: "avgExecuted", name: "Executed plan" },
        { key: "avgAverage", name: "Average plan" },
        { key: "avgBest", name: "Best plan" },
      ].map(({ key, name }) => ({
        name,
        type: "line",
        showSymbol: true,
        symbolSize: 6,
        data: data.scoreStats.map((row) => row[key as keyof typeof row]),
      })),
    };

    const modeShare: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Share",
        max: 1,
        axisLabel: {
          color: cssColors.textMuted,
          formatter: (value: number) => `${Math.round(value * 100)}%`,
        },
      },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => `${(Number(value) * 100).toFixed(1)}%`,
      },
      series: data.modeNames.map((mode) => ({
        name: displayMode(mode),
        type: "bar",
        stack: "share",
        data: data.modeShare.map((row) => row.values[mode] ?? 0),
      })),
    };

    const passengerKm: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Passenger-km",
        nameTextStyle: { color: cssColors.textMuted },
      },
      series: data.passengerKilometreModes.map((mode) => ({
        name: displayMode(mode),
        type: "bar",
        stack: "distance",
        data: data.passengerKilometres.map((row) => row.values[mode] ?? 0),
      })),
    };

    const passengerHours: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Passenger-hours",
        nameTextStyle: { color: cssColors.textMuted },
      },
      series: [
        {
          name: "Travelling",
          type: "bar",
          stack: "time",
          data: data.passengerHours.map((row) =>
            Object.values(row.travel).reduce((sum, value) => sum + value, 0),
          ),
        },
        {
          name: "Waiting / stage activity",
          type: "bar",
          stack: "time",
          data: data.passengerHours.map((row) =>
            Object.values(row.wait).reduce((sum, value) => sum + value, 0),
          ),
        },
      ],
    };

    const tripTimeValue = (
      iteration: number,
      mode: string,
      field: "averageTravelMinutes" | "averageWaitMinutes",
    ) =>
      data.tripTimeStats.find((row) => row.iteration === iteration)?.[field][
        mode
      ] ?? null;

    const averageTravelTime: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Average minutes / trip",
        nameTextStyle: { color: cssColors.textMuted },
      },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) =>
          value === null || value === undefined
            ? "No trips"
            : `${Number(value).toFixed(1)} min`,
      },
      series: data.tripTimeModes.map((mode) => ({
        name: displayMode(mode),
        type: "line",
        connectNulls: false,
        showSymbol: true,
        symbolSize: 6,
        data: data.availableIterations.map((iteration) =>
          tripTimeValue(iteration, mode, "averageTravelMinutes"),
        ),
      })),
    };

    const averageWaitTime: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Average waiting minutes / trip",
        nameTextStyle: { color: cssColors.textMuted },
      },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) =>
          value === null || value === undefined
            ? "No trips"
            : `${Number(value).toFixed(1)} min`,
      },
      series: data.tripTimeModes.map((mode) => ({
        name: displayMode(mode),
        type: "line",
        connectNulls: false,
        showSymbol: true,
        symbolSize: 6,
        data: data.availableIterations.map((iteration) =>
          tripTimeValue(iteration, mode, "averageWaitMinutes"),
        ),
      })),
    };

    const travelDistance: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Average distance (km)",
        nameTextStyle: { color: cssColors.textMuted },
      },
      series: [
        {
          name: "Leg distance",
          type: "line",
          showSymbol: true,
          data: data.travelDistance.map((row) => row.avgLegKm),
        },
        {
          name: "Trip distance",
          type: "line",
          showSymbol: true,
          data: data.travelDistance.map((row) => row.avgTripKm),
        },
      ],
    };

    const runtime: EChartsOption = {
      ...chartBase(),
      xAxis: baseXAxis(),
      yAxis: {
        ...baseYAxis(),
        name: "Runtime (seconds)",
        nameTextStyle: { color: cssColors.textMuted },
      },
      series: [
        {
          name: "MobSim",
          type: "bar",
          stack: "runtime",
          data: data.runtime.map((row) => row.mobsimSeconds),
        },
        {
          name: "Replanning",
          type: "bar",
          stack: "runtime",
          data: data.runtime.map((row) => row.replanningSeconds),
        },
        {
          name: "Total iteration",
          type: "line",
          data: data.runtime.map((row) => row.totalSeconds),
        },
      ],
    };
    return {
      scores,
      modeShare,
      passengerKm,
      passengerHours,
      averageTravelTime,
      averageWaitTime,
      travelDistance,
      runtime,
    };
  }, [data]);

  if (error) {
    return (
      <section className="view status-note">
        General MATSim results could not load: {error}
      </section>
    );
  }
  if (!data || !options) {
    return (
      <section className="view load-inline">
        <div className="spinner" />
        <span>Reading MATSim summary tables…</span>
      </section>
    );
  }

  const latestIteration = Math.max(...data.availableIterations);
  const latestScore = data.scoreStats.find(
    (row) => row.iteration === latestIteration,
  );
  const latestModes = data.modeShare.find(
    (row) => row.iteration === latestIteration,
  );
  const latestDistance = data.travelDistance.find(
    (row) => row.iteration === latestIteration,
  );

  return (
    <section className="view">
      <header className="view-heading">
        <div>
          <span className="eyebrow">Complete run overview</span>
          <h1>General MATSim results</h1>
          <p className="heading-description">
            Standard MATSim measures across all{" "}
            {data.availableIterations.length} iterations.
          </p>
        </div>
      </header>

      {data.tripTimeStats.length < data.availableIterations.length ? (
        <p className="method-note">
          Average travel and waiting times are available only for iterations {data.tripTimeStats.map((row) => row.iteration).join(", ")},
          where trip tables were saved. Gaps mean unavailable data, not zero travel or waiting time.
        </p>
      ) : null}

      <div className="metric-row">
        <Metric
          label={`Executed score · iteration ${latestIteration}`}
          value={latestScore?.avgExecuted.toFixed(2) ?? "—"}
          context="Average score of the plans executed in the final iteration."
        />
        <Metric
          label={`UAM mode share · iteration ${latestIteration}`}
          value={`${((latestModes?.values.uam ?? 0) * 100).toFixed(1)}%`}
          context="Share of recorded trips using UAM."
        />
        <Metric
          label={`Average trip distance · iteration ${latestIteration}`}
          value={`${latestDistance?.avgTripKm.toFixed(1) ?? "—"} km`}
          context="Average distance of a complete MATSim trip."
        />
      </div>

      <div className="results-grid">
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Score convergence</h2>
          </div>
          <EChart
            option={options.scores}
            height={300}
            label="MATSim score history by iteration"
          />
        </article>
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Mode share</h2>
          </div>
          <EChart
            option={options.modeShare}
            height={300}
            label="Mode share by MATSim iteration"
          />
        </article>
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Passenger kilometres</h2>
          </div>
          <EChart
            option={options.passengerKm}
            height={300}
            label="Passenger kilometres by mode and iteration"
          />
        </article>
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Average travel time by mode</h2>
          </div>
          <EChart
            option={options.averageTravelTime}
            height={300}
            label="Average trip travel time by main mode and MATSim iteration"
          />
        </article>
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Average waiting time by mode</h2>
          </div>
          <EChart
            option={options.averageWaitTime}
            height={300}
            label="Average trip waiting time by main mode and MATSim iteration"
          />
        </article>
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Average travel distance</h2>
          </div>
          <EChart
            option={options.travelDistance}
            height={300}
            label="Average leg and trip distance by iteration"
          />
        </article>
        <article>
          <div className="section-heading section-heading--compact">
            <h2>Passenger hours</h2>
          </div>
          <EChart
            option={options.passengerHours}
            height={300}
            label="Passenger travel and waiting hours by iteration"
          />
        </article>
        <article className="results-grid__wide">
          <div className="section-heading section-heading--compact">
            <h2>Simulation runtime</h2>
          </div>
          <EChart
            option={options.runtime}
            height={300}
            label="MATSim runtime by iteration"
          />
        </article>
      </div>

      <p className="method-note">
        Read directly from: {data.sourceFiles.join(", ")}.
      </p>
    </section>
  );
}
