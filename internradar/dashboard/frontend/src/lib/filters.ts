import type { JobQuery } from "./types";

export function buildQueryString(query: JobQuery): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  return params.toString();
}

export function emptyQuery(): JobQuery {
  return {
    sort: "opportunity_score",
    limit: 250,
    offset: 0,
  };
}
