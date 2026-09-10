import type {
  AnalyticsBundle,
  GeneralMatsimResults,
  IterationCatalog,
} from "./types";

const SUPPORTED_ANALYTICS_SCHEMA = 8;

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail || `Module 5 request failed (${response.status})`,
    );
  }
  return (await response.json()) as T;
}

export async function loadAnalytics(
  iteration?: number | null,
): Promise<AnalyticsBundle> {
  const query = iteration === null || iteration === undefined
    ? ""
    : `?iteration=${iteration}`;
  const data = await getJson<AnalyticsBundle>(`/api/analytics${query}`);
  if (data.schemaVersion !== SUPPORTED_ANALYTICS_SCHEMA) {
    throw new Error(`Unsupported analytics schema ${data.schemaVersion}`);
  }
  return data;
}

export function loadIterations(): Promise<IterationCatalog> {
  return getJson<IterationCatalog>("/api/iterations");
}

export function loadGeneralMatsimResults(): Promise<GeneralMatsimResults> {
  return getJson<GeneralMatsimResults>("/api/matsim-results");
}
