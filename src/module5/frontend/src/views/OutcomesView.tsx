import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { AnalyticsBundle } from "../types";
import { cssColors } from "../theme";
import { EChart } from "../components/EChart";
import { Metric } from "../components/Metric";

interface OutcomesViewProps {
  data: AnalyticsBundle;
}

function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function OutcomesView({ data }: OutcomesViewProps) {
  const outcomeOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [cssColors.air, cssColors.ground, cssColors.pt, cssColors.muted],
      grid: { left: 115, right: 32, top: 24, bottom: 42 },
      legend: {
        bottom: 0,
        textStyle: { color: cssColors.textMuted },
      },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      xAxis: {
        type: "value",
        name: "Eligible travellers",
        minInterval: 1,
        axisLabel: { color: cssColors.textMuted },
        nameTextStyle: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      yAxis: {
        type: "category",
        data: data.outcomes.byUrgency.map((group) => titleCase(group.urgency)),
        axisLabel: { color: cssColors.text },
      },
      series: [
        {
          name: "UAM completed",
          type: "bar",
          stack: "outcome",
          data: data.outcomes.byUrgency.map((group) => group.uamCompleted),
        },
        {
          name: "Car selected",
          type: "bar",
          stack: "outcome",
          data: data.outcomes.byUrgency.map((group) => group.carSelected),
        },
        {
          name: "Scheduled PT selected",
          type: "bar",
          stack: "outcome",
          data: data.outcomes.byUrgency.map((group) => group.ptSelected),
        },
        {
          name: "Unobserved",
          type: "bar",
          stack: "outcome",
          data: data.outcomes.byUrgency.map((group) => group.unobserved),
        },
      ],
    }),
    [data.outcomes],
  );

  const travelOption = useMemo<EChartsOption>(() => {
    const groups = ["uam", "car", "pt"] as const;
    const averages = groups.map((outcome) => {
      const values = data.journeys
        .filter(
          (journey) =>
            journey.outcome === outcome && journey.travelTimeSeconds !== null,
        )
        .map((journey) => journey.travelTimeSeconds as number);
      return values.length
        ? values.reduce((sum, value) => sum + value, 0) / values.length / 60
        : 0;
    });
    return {
      animation: false,
      color: [cssColors.air, cssColors.ground, cssColors.pt],
      grid: { left: 58, right: 18, top: 20, bottom: 42 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => `${Number(value).toFixed(1)} min`,
      },
      xAxis: {
        type: "category",
        data: ["UAM completed", "Car selected", "Scheduled PT selected"],
        axisLabel: { color: cssColors.textMuted },
      },
      yAxis: {
        type: "value",
        name: "Mean journey time (min)",
        axisLabel: { color: cssColors.textMuted },
        nameTextStyle: { color: cssColors.textMuted },
        splitLine: { lineStyle: { color: cssColors.grid } },
      },
      series: [
        {
          type: "bar",
          data: averages.map((value, index) => ({
            value: Number(value.toFixed(2)),
            itemStyle: {
              color: [cssColors.air, cssColors.ground, cssColors.pt][index],
            },
          })),
          barMaxWidth: 70,
        },
      ],
    };
  }, [data.journeys]);

  return (
    <section className="view">
      <header className="view-heading">
        <div>
          <span className="eyebrow">Traveller decisions</span>
          <h1>UAM retention and journey outcomes</h1>
        </div>
      </header>

      <div className="metric-row metric-row--four">
        <Metric
          label="Eligible travellers"
          value={String(data.outcomes.eligibleTravellers)}
          context="travellers with a UAM plan alternative"
        />
        <Metric
          label="Completed UAM"
          value={String(data.outcomes.uamCompleted)}
          context={`${(
            (data.outcomes.uamCompleted / Math.max(1, data.outcomes.eligibleTravellers)) *
            100
          ).toFixed(1)}% retained`}
          tone="success"
        />
        <Metric
          label="Scheduled PT selected"
          value={String(data.outcomes.ptSelected)}
          context="executed public-transport journeys"
        />
        <Metric
          label="Non-UAM outcome rate"
          value={`${(data.outcomes.abandonmentRate * 100).toFixed(1)}%`}
          context={`${data.outcomes.carSelected} car, ${data.outcomes.ptSelected} PT, ${data.outcomes.unobserved} unobserved`}
          tone="warning"
        />
      </div>

      <p className="method-note">{data.outcomes.definition}</p>

      <div className="split-grid split-grid--wide">
        <div>
          <div className="section-heading section-heading--compact">
            <div>
              <span className="eyebrow">Urgency segmentation</span>
              <h2>Observed mode outcome</h2>
            </div>
          </div>
          <EChart
            option={outcomeOption}
            height={360}
            label="UAM, car, scheduled PT, and unobserved outcomes by urgency"
          />
        </div>
        <div>
          <div className="section-heading section-heading--compact">
            <div>
              <span className="eyebrow">Experienced performance</span>
              <h2>Mean end-to-end journey time</h2>
            </div>
          </div>
          <EChart
            option={travelOption}
            height={360}
            label="Mean end-to-end journey time by observed outcome"
          />
        </div>
      </div>
    </section>
  );
}
