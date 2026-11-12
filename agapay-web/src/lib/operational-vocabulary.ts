/** Display vocabulary only. Wire enums and incident lifecycles remain unchanged. */
export const operationalVocabulary = {
  observed: "Observed",
  lastKnown: "Last known",
  noValidReading: "No valid reading",
  experimentalProjection: "Experimental projection",
  officialAdvisory: "Official advisory",
  practiceSos: "SOS",
} as const;

export function readingLabel(value: number | null, current: boolean, measuredAt: string | null): string {
  if (value === null) return operationalVocabulary.noValidReading;
  // A value without measurement time cannot be presented as an observation now.
  return current && measuredAt !== null && Number.isFinite(Date.parse(measuredAt))
    ? operationalVocabulary.observed : operationalVocabulary.lastKnown;
}
