import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#0B3D91',
          primaryDark: '#062254',
          primaryLight: '#1E5BBF',
          secondary: '#1976D2',
          secondaryLight: '#E3F2FD',
        },
        surface: {
          bg: '#F5F7FA',
          card: '#FFFFFF',
          secondary: '#F1F5F9',
        },
        typography: {
          primary: '#172033',
          secondary: '#64748B',
          muted: '#94A3B8',
        },
        border: {
          light: '#E2E8F0',
          hover: '#CBD5E1',
        },
        alert: {
          normal: '#16A34A',
          normalBg: '#DCFCE7',
          normalText: '#14532D',

          advisory: '#EAB308',
          advisoryBg: '#FEF9C3',
          advisoryText: '#713F12',

          warning: '#F97316',
          warningBg: '#FFEDD5',
          warningText: '#7C2D12',

          evacuate: '#DC2626',
          evacuateBg: '#FEE2E2',
          evacuateText: '#7F1D1D',

          sos: '#E11D48',
          sosBg: '#FFE4E6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03)',
        cardHover: '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -1px rgba(0, 0, 0, 0.04)',
      },
    },
  },
  plugins: [],
};

export default config;
