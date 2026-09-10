import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";
import {
  PathLayer,
  PolygonLayer,
  ScatterplotLayer,
  TextLayer,
} from "@deck.gl/layers";
import type { AnalyticsBundle, Fato, Stand } from "../types";
import { palette } from "../theme";
import { Metric } from "../components/Metric";

interface VertiportViewProps {
  data: AnalyticsBundle;
}

function rectangle(
  center: [number, number],
  width: number,
  height: number,
): [number, number][] {
  const halfWidth = width / 2;
  const halfHeight = height / 2;
  return [
    [center[0] - halfWidth, center[1] - halfHeight],
    [center[0] + halfWidth, center[1] - halfHeight],
    [center[0] + halfWidth, center[1] + halfHeight],
    [center[0] - halfWidth, center[1] + halfHeight],
  ];
}

export function VertiportView({ data }: VertiportViewProps) {
  const [selectedId, setSelectedId] = useState(data.vertiports[0]?.id ?? "");
  const selected =
    data.vertiports.find((vertiport) => vertiport.id === selectedId) ??
    data.vertiports[0];

  const layers = useMemo(() => {
    if (!selected) return [];
    const coreNodes = selected.nodes.filter(
      (node) => !["stand", "fato"].includes(node.kind),
    );
    const stationStand = selected.stationStandId;
    return [
      new PathLayer({
        id: "vertiport-links",
        data: selected.links,
        getPath: (link) => link.path,
        getColor: (link) =>
          link.modes.includes("uam")
            ? [...palette.air, 150]
            : [...palette.structure, 150],
        getWidth: (link) => (link.modes === "uam" ? 4 : 2),
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        pickable: true,
      }),
      new PolygonLayer<Stand>({
        id: "stands",
        data: selected.stands,
        getPolygon: (stand) =>
          rectangle(stand.position, stand.dimension_m, stand.dimension_m),
        getFillColor: (stand) =>
          stand.id === stationStand
            ? [...palette.boarding, 175]
            : [...palette.ground, 45],
        getLineColor: (stand) =>
          stand.id === stationStand
            ? [...palette.boarding, 230]
            : [...palette.ground, 120],
        lineWidthMinPixels: 1,
        stroked: true,
        pickable: true,
      }),
      new PolygonLayer<Fato>({
        id: "fato-safety",
        data: selected.fatos,
        getPolygon: (fato) =>
          rectangle(
            fato.position,
            fato.width_m + fato.safety_margin_m * 2,
            fato.length_m + fato.safety_margin_m * 2,
          ),
        getFillColor: [...palette.air, 35],
        getLineColor: [...palette.air, 110],
        lineWidthMinPixels: 1,
        stroked: true,
      }),
      new PolygonLayer<Fato>({
        id: "fato",
        data: selected.fatos,
        getPolygon: (fato) =>
          rectangle(fato.position, fato.width_m, fato.length_m),
        getFillColor: [...palette.air, 100],
        getLineColor: [...palette.air, 240],
        lineWidthMinPixels: 2,
        stroked: true,
        pickable: true,
      }),
      new ScatterplotLayer({
        id: "core-nodes",
        data: coreNodes,
        getPosition: (node) => node.position,
        getRadius: 4,
        radiusUnits: "pixels",
        getFillColor: (node) =>
          node.kind === "airborne"
            ? [...palette.air, 230]
            : [...palette.terminal, 230],
        getLineColor: [221, 235, 242, 220],
        lineWidthMinPixels: 1,
        stroked: true,
        pickable: true,
      }),
      new TextLayer({
        id: "core-labels",
        data: coreNodes,
        getPosition: (node) => node.position,
        getText: (node) => node.label.replace(/\s+\d+$/, ""),
        getSize: 12,
        sizeUnits: "pixels",
        getColor: [220, 233, 240, 245],
        getPixelOffset: [0, -13],
        getTextAnchor: "middle",
        fontWeight: 500,
      }),
      new TextLayer<Stand>({
        id: "stand-labels",
        data: selected.stands,
        getPosition: (stand) => stand.position,
        getText: (stand) => stand.id,
        getSize: 10,
        sizeUnits: "pixels",
        getColor: [204, 220, 229, 230],
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
      }),
      new TextLayer<Fato>({
        id: "fato-labels",
        data: selected.fatos,
        getPosition: (fato) => fato.position,
        getText: (fato) => `FATO ${fato.id}`,
        getSize: 11,
        sizeUnits: "pixels",
        getColor: [238, 242, 244, 255],
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
        fontWeight: 500,
      }),
    ];
  }, [selected]);

  if (!selected) {
    return <section className="view">No vertiport design report was found.</section>;
  }

  const centerX = (selected.bounds.minX + selected.bounds.maxX) / 2;
  const centerY = (selected.bounds.minY + selected.bounds.maxY) / 2;
  const width = Math.max(1, selected.bounds.maxX - selected.bounds.minX);
  const zoom = Math.max(0.3, Math.min(2.0, Math.log2(700 / width)));

  return (
    <section className="view">
      <header className="view-heading">
        <div>
          <span className="eyebrow">Generated topology</span>
          <h1>Vertiport layout and internal links</h1>
        </div>
        <div className="segmented-control" aria-label="Select vertiport">
          {data.vertiports.map((vertiport) => (
            <button
              key={vertiport.id}
              type="button"
              className={vertiport.id === selected.id ? "is-active" : ""}
              onClick={() => setSelectedId(vertiport.id)}
            >
              {vertiport.name}
            </button>
          ))}
        </div>
      </header>

      <div className="metric-row">
        <Metric
          label="Physical stands"
          value={String(selected.standCount)}
          context={`Station interface: ${selected.stationStandId}`}
        />
        <Metric
          label="FATO resources"
          value={String(selected.fatoCount)}
          context={`${selected.fatoCapacityVehPerHour} movements/hour design capacity`}
        />
        <Metric
          label="Taxi-route widths"
          value={`${selected.groundTaxiRouteWidthM} / ${selected.airTaxiRouteWidthM} m`}
          context="ground / air"
        />
      </div>

      <div className="plan-frame">
        <DeckGL
          key={selected.id}
          views={new OrthographicView({ id: "plan" })}
          initialViewState={{
            target: [centerX, centerY, 0],
            zoom,
            minZoom: -1,
            maxZoom: 4,
          }}
          controller
          layers={layers}
          getTooltip={({ object }) =>
            object
              ? {
                  text:
                    object.label ??
                    (object.dimension_m
                      ? `Stand ${object.id}\n${object.dimension_m} m`
                      : object.length_m
                        ? `FATO ${object.id}\n${object.length_m} × ${object.width_m} m`
                        : object.id),
                }
              : null
          }
        />
        <div className="plan-legend">
          <span><i className="legend-line legend-line--walk" />Passenger link</span>
          <span><i className="legend-line legend-line--uam" />UAM movement link</span>
          <span><i className="legend-square legend-square--station" />Station stand</span>
          <span><i className="legend-square legend-square--fato" />FATO</span>
        </div>
      </div>
      <p className="method-note">
        This plan is generated from the current MATSim network and vertiport design
        report; pan and zoom to inspect links, nodes, stand dimensions and FATO
        safety areas.
      </p>
    </section>
  );
}
