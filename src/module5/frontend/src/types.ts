export type ViewName =
  | "journey"
  | "operations"
  | "outcomes"
  | "matsim"
  | "vertiport";

export interface RunInfo {
  id: string;
  iteration: number | null;
  generatedAt: string;
  sourceSignature: string;
  eventsFile: string;
  networkFile: string;
  crs: string;
  startTime: number;
  endTime: number;
  durationSeconds: number;
  eventCount: number;
  eventTypes: Record<string, number>;
  warnings: string[];
  backgroundTrafficEnabled: boolean;
}

export interface IterationOption {
  number: number;
  label: string;
  eventsFile: string;
}

export interface IterationCatalog {
  scenarioName?: string | null;
  defaultIteration: number | null;
  iterations: IterationOption[];
}

export interface ValuesByMode {
  iteration: number;
  values: Record<string, number>;
}

export interface GeneralMatsimResults {
  availableIterations: number[];
  scoreStats: {
    iteration: number;
    avgExecuted: number;
    avgWorst: number;
    avgAverage: number;
    avgBest: number;
  }[];
  modeShare: ValuesByMode[];
  modeNames: string[];
  passengerKilometres: ValuesByMode[];
  passengerKilometreModes: string[];
  passengerHours: {
    iteration: number;
    travel: Record<string, number>;
    wait: Record<string, number>;
  }[];
  tripTimeStats: {
    iteration: number;
    averageTravelMinutes: Record<string, number>;
    averageWaitMinutes: Record<string, number>;
    tripCounts: Record<string, number>;
  }[];
  tripTimeModes: string[];
  travelDistance: {
    iteration: number;
    avgLegKm: number;
    avgTripKm: number;
  }[];
  runtime: {
    iteration: number;
    totalSeconds: number;
    mobsimSeconds: number;
    replanningSeconds: number;
  }[];
  sourceFiles: string[];
}

export interface Trajectory {
  id: string;
  vehicleId: string;
  mode: "walk" | "car" | "bus" | "train" | "pt" | "uam";
  isBackground: boolean;
  startTime: number;
  endTime: number;
  path: [number, number][];
  timestamps: number[];
  linkCount: number;
  occupancy: {
    time: number;
    count: number;
    passengerIds: string[];
  }[];
}

export interface Landmark {
  id: string;
  label: string;
  kind: "origin" | "vertiport";
  position: [number, number];
}

export interface QueueStage {
  key: keyof QueueSample;
  label: string;
  unit: string;
  definition: string;
}

export interface QueueSample {
  time: number;
  terminalProcessing: number;
  uamDispatch: number;
  boardingHold: number;
  fatoOccupancy: number;
}

export interface FatoOccupancyFacility {
  vertiportId: string;
  name: string;
  series: {
    time: number;
    occupancy: number;
  }[];
}

export interface WaitTime {
  personId: string;
  urgency: string;
  waitSeconds: number;
  completed: boolean;
}

export interface Journey {
  personId: string;
  urgency: string;
  outcome: "uam" | "pt" | "car" | "unobserved";
  departureTime: number | null;
  arrivalTime: number | null;
  travelTimeSeconds: number | null;
}

export interface OutcomeGroup {
  urgency: string;
  eligible: number;
  uamCompleted: number;
  carSelected: number;
  ptSelected: number;
  unobserved: number;
  abandonmentRate: number;
}

export interface Outcomes {
  definition: string;
  eligibleTravellers: number;
  uamCompleted: number;
  carSelected: number;
  ptSelected: number;
  unobserved: number;
  abandonmentRate: number;
  byUrgency: OutcomeGroup[];
}

export interface CapacitySample {
  time: number;
  movementsLastHour: number;
  capacityVehPerHour: number;
  utilisation: number;
  breach: boolean;
}

export interface Capacity {
  definition: string;
  fatoCapacityVehPerHour: number;
  movementCount: number;
  breachProportion: number;
  series: CapacitySample[];
  headwayDefinition: string;
  headwayComparisonCount: number;
  headwayViolationCount: number;
  headwayViolationProportion: number;
  minimumObservedSeparationSeconds: number | null;
  headwaySeries: {
    time: number;
    previousMovementTime: number;
    vertiportId: string;
    fatoId: string;
    name: string;
    separationSeconds: number;
    requiredSeparationSeconds: number;
    compliant: boolean;
    vehicleId: string;
    movementType: string;
  }[];
  byVertiport: {
    vertiportId: string;
    name: string;
    fatoCapacityVehPerHour: number;
    movementCount: number;
    breachProportion: number;
    tSepSeconds: number;
    headwayComparisonCount: number;
    headwayViolationCount: number;
    headwayViolationProportion: number;
    minimumObservedSeparationSeconds: number | null;
    series: CapacitySample[];
  }[];
  byFato: {
    vertiportId: string;
    fatoId: string;
    name: string;
    tSepSeconds: number;
    fatoCapacityVehPerHour: number;
    movementCount: number;
    headwayComparisonCount: number;
    headwayViolationCount: number;
    headwayViolationProportion: number;
    minimumObservedSeparationSeconds: number | null;
  }[];
}

export interface VertiportNode {
  id: string;
  label: string;
  kind: string;
  position: [number, number];
  geographicPosition: [number, number];
}

export interface VertiportLink {
  id: string;
  source: string;
  target: string;
  capacity: number;
  modes: string;
  path: [number, number][];
}

export interface Stand {
  id: string;
  center: [number, number];
  position: [number, number];
  dimension_m: number;
  protection_margin_m: number;
}

export interface Fato {
  id: string;
  center: [number, number];
  position: [number, number];
  elevated: boolean;
  length_m: number;
  width_m: number;
  tlof_length_m: number;
  tlof_width_m: number;
  safety_margin_m: number;
}

export interface Vertiport {
  id: string;
  name: string;
  standCount: number;
  stationStandId: string;
  fatoCount: number;
  fatoCapacityVehPerHour: number;
  groundTaxiRouteWidthM: number;
  airTaxiRouteWidthM: number;
  stands: Stand[];
  fatos: Fato[];
  nodes: VertiportNode[];
  links: VertiportLink[];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
}

export interface AnalyticsBundle {
  schemaVersion: number;
  run: RunInfo;
  bounds: {
    west: number;
    south: number;
    east: number;
    north: number;
  };
  landmarks: Landmark[];
  trajectories: Trajectory[];
  queueStages: QueueStage[];
  queueSeries: QueueSample[];
  fatoOccupancyByVertiport: FatoOccupancyFacility[];
  waitTimes: WaitTime[];
  journeys: Journey[];
  outcomes: Outcomes;
  capacity: Capacity;
  vertiports: Vertiport[];
}
