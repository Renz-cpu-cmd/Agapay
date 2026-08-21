'use client';

import React from 'react';
import { PredictionPoint } from '@/models/telemetry';
import { Brain, TrendingUp, AlertTriangle } from 'lucide-react';

interface PredictionChartProps {
  predictions: PredictionPoint[];
  currentDepth: number;
  evacuateThreshold?: number;
}

export function PredictionChart({
  predictions,
  currentDepth,
  evacuateThreshold = 90,
}: PredictionChartProps) {
  return (
    <div className="bg-white rounded-xl p-5 border border-brand-secondary/30 shadow-card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-brand-secondaryLight text-brand-primary">
            <Brain size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-extrabold text-typography-primary">AI / ML Predictive Hydrodynamic Forecast</h4>
              <span className="px-2 py-0.5 text-[10px] font-black bg-blue-100 text-blue-800 rounded uppercase">
                ML PREDICTION
              </span>
            </div>
            <p className="text-xs text-typography-secondary">
              Recurrent LSTM neural network estimation based on upstream catchment run-off
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {predictions.map((p, idx) => {
          const diff = p.predictedDepthCm - currentDepth;
          const isDanger = p.predictedDepthCm >= evacuateThreshold;

          return (
            <div
              key={idx}
              className={`p-4 rounded-xl border transition-all ${
                isDanger
                  ? 'bg-alert-evacuateBg/40 border-alert-evacuate/40'
                  : 'bg-surface-secondary/70 border-border-light'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-black text-brand-primary uppercase tracking-wider">
                  {p.timeLabel}
                </span>
                {diff > 0 ? (
                  <span className="flex items-center text-xs font-bold text-alert-warning gap-1">
                    <TrendingUp size={14} /> +{diff.toFixed(1)} cm
                  </span>
                ) : (
                  <span className="text-xs font-bold text-alert-normal">{diff.toFixed(1)} cm</span>
                )}
              </div>

              <div className="mt-2">
                <div className="text-2xl font-black text-typography-primary">
                  {p.predictedDepthCm}{' '}
                  <span className="text-xs font-semibold text-typography-secondary">cm</span>
                </div>
                <div className="text-xs text-typography-muted mt-0.5 font-medium">
                  Confidence: {p.confidenceInterval[0]} – {p.confidenceInterval[1]} cm
                </div>
                <div className="text-xs text-typography-secondary mt-1">
                  Est. Rain: <strong>{p.rainfallEstimatedMm} mm/h</strong>
                </div>
              </div>

              {isDanger && (
                <div className="mt-3 flex items-center gap-1.5 text-xs font-bold text-alert-evacuate bg-white/80 p-2 rounded-lg border border-alert-evacuate/20">
                  <AlertTriangle size={14} />
                  <span>Crosses Evacuate Threshold!</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-typography-muted mt-4 bg-surface-secondary p-2.5 rounded-lg border border-border-light leading-relaxed">
        <strong>Notice to Command Staff:</strong> ML Predictions are statistical hydrodynamic projections. All disaster response actions must align with verified ground sensor telemetry and official NDRRMC directives.
      </p>
    </div>
  );
}
