export type ReportType = 'FloodEvent' | 'StationPerformance' | 'AlertHistory' | 'SOSLog';

export interface ReportFilter {
  reportType: ReportType;
  stationId?: string;
  barangay?: string;
  startDate: string;
  endDate: string;
}

export interface GeneratedReport {
  id: string;
  title: string;
  type: ReportType;
  generatedAt: string;
  generatedBy: string;
  summary: {
    totalAlerts: number;
    peakWaterLevelCm: number;
    peakStationName: string;
    totalRainfallMm: number;
    sosIncidentsCount: number;
    averageResponseMinutes: number;
  };
  rows: Array<Record<string, any>>;
}
