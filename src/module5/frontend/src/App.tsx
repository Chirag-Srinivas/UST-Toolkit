import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  LayoutGrid,
  Route,
  Users,
} from "lucide-react";
import {
  loadAnalytics,
  loadGeneralMatsimResults,
  loadIterations,
} from "./api";
import type {
  AnalyticsBundle,
  GeneralMatsimResults,
  IterationCatalog,
  ViewName,
} from "./types";
import { JourneyView } from "./views/JourneyView";
import { MatsimResultsView } from "./views/MatsimResultsView";
import { OperationsView } from "./views/OperationsView";
import { OutcomesView } from "./views/OutcomesView";
import { VertiportView } from "./views/VertiportView";

const navigation: {
  id: ViewName;
  label: string;
  icon: typeof Route;
}[] = [
  { id: "journey", label: "Journey playback", icon: Route },
  { id: "operations", label: "Operations", icon: Activity },
  { id: "outcomes", label: "Passenger outcomes", icon: Users },
  { id: "matsim", label: "General MATSim results", icon: BarChart3 },
  { id: "vertiport", label: "Vertiport layout", icon: LayoutGrid },
];

function showcasePlaybackTime(bundle: AnalyticsBundle): number {
  const passengerCars = bundle.trajectories.filter(
    (trajectory) => trajectory.mode === "car" && !trajectory.isBackground,
  );
  if (passengerCars.length) {
    // Background demand can start well before the scenario passengers. Open
    // when the last passenger car has entered the network so the complete
    // configured cohort is visible immediately.
    return Math.max(...passengerCars.map((trajectory) => trajectory.startTime));
  }

  const passengerMovements = bundle.trajectories.filter(
    (trajectory) =>
      !trajectory.isBackground &&
      (trajectory.mode === "walk" || trajectory.mode === "uam"),
  );
  if (passengerMovements.length) {
    return Math.min(
      ...passengerMovements.map((trajectory) => trajectory.startTime),
    );
  }
  return bundle.run.startTime;
}

export default function App() {
  const [data, setData] = useState<AnalyticsBundle | null>(null);
  const [catalog, setCatalog] = useState<IterationCatalog | null>(null);
  const [selectedIteration, setSelectedIteration] = useState<number | null>(null);
  const [iterationLoading, setIterationLoading] = useState(false);
  const [generalResults, setGeneralResults] =
    useState<GeneralMatsimResults | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewName>("journey");
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);

  useEffect(() => {
    loadIterations()
      .then(async (available) => {
        setCatalog(available);
        setSelectedIteration(available.defaultIteration);
        return loadAnalytics(available.defaultIteration);
      })
      .then((bundle) => {
        setData(bundle);
        setCurrentTime(showcasePlaybackTime(bundle));
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : String(reason)),
      );
  }, []);

  useEffect(() => {
    loadGeneralMatsimResults()
      .then(setGeneralResults)
      .catch((reason: unknown) =>
        setGeneralError(reason instanceof Error ? reason.message : String(reason)),
      );
  }, []);

  const changeIteration = async (iteration: number) => {
    if (iteration === selectedIteration || iterationLoading) return;
    setIterationLoading(true);
    setPlaying(false);
    setError(null);
    try {
      const bundle = await loadAnalytics(iteration);
      setData(bundle);
      setSelectedIteration(iteration);
      setCurrentTime(showcasePlaybackTime(bundle));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setIterationLoading(false);
    }
  };

  useEffect(() => {
    if (!playing || !data) return;
    let animationFrame = 0;
    let previous = performance.now();
    const advance = (now: number) => {
      const elapsed = (now - previous) / 1000;
      previous = now;
      setCurrentTime((time) => {
        const next = time + elapsed * speed;
        if (next >= data.run.endTime) {
          setPlaying(false);
          return data.run.endTime;
        }
        return next;
      });
      animationFrame = requestAnimationFrame(advance);
    };
    animationFrame = requestAnimationFrame(advance);
    return () => cancelAnimationFrame(animationFrame);
  }, [playing, speed, data]);

  if (error) {
    return (
      <main className="load-state">
        <AlertTriangle size={28} />
        <h1>Module 5 could not load</h1>
        <p>{error}</p>
        <p>Confirm that the extractor has completed and the local server is running.</p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="load-state">
        <div className="spinner" />
        <p>Preparing simulation analytics…</p>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">UST</span>
          <div>
            <strong>Module 5</strong>
            <span>Simulation analytics</span>
          </div>
        </div>
        <nav aria-label="Module 5 views">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                className={view === item.id ? "is-active" : ""}
                onClick={() => setView(item.id)}
                aria-current={view === item.id ? "page" : undefined}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar__run">
          <span className="run-status"><i />Processed run</span>
          <strong>{catalog?.scenarioName || data.run.id}</strong>
          {selectedIteration !== null ? <span>Iteration {selectedIteration}</span> : null}
          <span>{data.run.eventCount.toLocaleString()} events</span>
          <span>{data.trajectories.length} movement trajectories</span>
        </div>
      </aside>

      <main className="content">
        {data.run.warnings.length ? (
          <div className="warning-strip">
            <AlertTriangle size={16} />
            {data.run.warnings.join(" ")}
          </div>
        ) : null}
        {view === "journey" ? (
          <JourneyView
            data={data}
            currentTime={currentTime}
            playing={playing}
            speed={speed}
            resetTime={showcasePlaybackTime(data)}
            onTimeChange={setCurrentTime}
            onPlayingChange={setPlaying}
            onSpeedChange={setSpeed}
            iterations={catalog?.iterations ?? []}
            selectedIteration={selectedIteration}
            iterationLoading={iterationLoading}
            onIterationChange={changeIteration}
          />
        ) : null}
        {view === "operations" ? <OperationsView data={data} /> : null}
        {view === "outcomes" ? <OutcomesView data={data} /> : null}
        {view === "matsim" ? (
          <MatsimResultsView data={generalResults} error={generalError} />
        ) : null}
        {view === "vertiport" ? <VertiportView data={data} /> : null}
      </main>
    </div>
  );
}
