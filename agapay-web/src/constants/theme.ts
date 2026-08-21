export type AlertLevel = 'NORMAL' | 'ADVISORY' | 'WARNING' | 'EVACUATE';

export interface AlertLevelConfig {
  code: AlertLevel;
  label: string;
  color: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
  description: string;
  recommendedAction: string;
}

export const ALERT_CONFIGS: Record<AlertLevel, AlertLevelConfig> = {
  NORMAL: {
    code: 'NORMAL',
    label: 'Normal',
    color: '#16A34A',
    bgColor: '#DCFCE7',
    textColor: '#14532D',
    borderColor: '#86EFAC',
    description: 'Water levels within safe operational limits.',
    recommendedAction: 'Maintain standard routine monitoring.',
  },
  ADVISORY: {
    code: 'ADVISORY',
    label: 'Advisory',
    color: '#EAB308',
    bgColor: '#FEF9C3',
    textColor: '#713F12',
    borderColor: '#FDE047',
    description: 'Water level rising due to precipitation.',
    recommendedAction: 'Monitor localized telemetry and broadcast advisories.',
  },
  WARNING: {
    code: 'WARNING',
    label: 'Warning',
    color: '#F97316',
    bgColor: '#FFEDD5',
    textColor: '#7C2D12',
    borderColor: '#FDBA74',
    description: 'Approaching critical riverbank capacity.',
    recommendedAction: 'Place rescue personnel on standby; prepare shelter mobilization.',
  },
  EVACUATE: {
    code: 'EVACUATE',
    label: 'Evacuate',
    color: '#DC2626',
    bgColor: '#FEE2E2',
    textColor: '#7F1D1D',
    borderColor: '#FCA5A5',
    description: 'Immediate flood threat detected at monitoring station!',
    recommendedAction: 'Execute mandatory community evacuation immediately.',
  },
};

export const APP_CONFIG = {
  appName: 'AGAPAY',
  systemName: 'Community Flood & Disaster Early-Warning System',
  jurisdiction: 'Bulacan / Central Luzon DRRM Command',
  version: 'v1.4.0 (Enterprise LGU Edition)',
  hotlines: {
    nationalEmergency: '911',
    ndrrmc: '(02) 8911-5061',
    redCross: '143',
    localBDRRMC: '(044) 791-0523',
  },
};
