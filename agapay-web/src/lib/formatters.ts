import { format, formatDistanceToNow } from 'date-fns';

export function formatWaterLevel(depthCm: number): string {
  if (depthCm >= 100) {
    const meters = depthCm / 100;
    return `${meters.toFixed(2)} m`;
  }
  return `${depthCm.toFixed(1)} cm`;
}

export function formatRainfall(rainfallMm: number): string {
  return `${rainfallMm.toFixed(1)} mm/h`;
}

export function formatBattery(batteryPercent: number): string {
  return `${batteryPercent}%`;
}

export function formatDateTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return format(d, 'MMM d, yyyy · HH:mm:ss');
}

export function formatTimeOnly(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return format(d, 'HH:mm:ss');
}

export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return formatDistanceToNow(d, { addSuffix: true });
}

export function formatCoordinates(lat: number, lng: number): string {
  return `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`;
}
