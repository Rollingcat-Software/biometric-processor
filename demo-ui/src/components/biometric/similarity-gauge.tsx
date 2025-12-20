'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

interface SimilarityGaugeProps {
  value: number; // 0-1
  threshold?: number; // 0-1
  size?: 'sm' | 'md' | 'lg';
  showPercentage?: boolean;
  showLabel?: boolean;
  className?: string;
}

export function SimilarityGauge({
  value,
  threshold = 0.6,
  size = 'md',
  showPercentage = true,
  showLabel = true,
  className,
}: SimilarityGaugeProps) {
  const percentage = Math.round(value * 100);
  const isMatch = value >= threshold;

  const sizeConfig = {
    sm: { width: 120, height: 80, strokeWidth: 8, fontSize: 'text-lg' },
    md: { width: 180, height: 120, strokeWidth: 12, fontSize: 'text-2xl' },
    lg: { width: 240, height: 160, strokeWidth: 16, fontSize: 'text-4xl' },
  };

  const config = sizeConfig[size];
  const radius = (config.width - config.strokeWidth) / 2;
  const circumference = Math.PI * radius; // Half circle
  const strokeDashoffset = circumference - (value * circumference);

  const getColor = () => {
    if (value >= 0.8) return { stroke: '#22c55e', bg: 'bg-green-500/10', text: 'text-green-600' };
    if (value >= 0.6) return { stroke: '#84cc16', bg: 'bg-lime-500/10', text: 'text-lime-600' };
    if (value >= 0.4) return { stroke: '#eab308', bg: 'bg-yellow-500/10', text: 'text-yellow-600' };
    if (value >= 0.2) return { stroke: '#f97316', bg: 'bg-orange-500/10', text: 'text-orange-600' };
    return { stroke: '#ef4444', bg: 'bg-red-500/10', text: 'text-red-600' };
  };

  const colors = getColor();

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <div className="relative" style={{ width: config.width, height: config.height }}>
        {/* Background arc */}
        <svg
          width={config.width}
          height={config.height}
          className="overflow-visible"
        >
          <path
            d={`M ${config.strokeWidth / 2} ${config.height} A ${radius} ${radius} 0 0 1 ${config.width - config.strokeWidth / 2} ${config.height}`}
            fill="none"
            stroke="currentColor"
            strokeWidth={config.strokeWidth}
            className="text-muted/20"
            strokeLinecap="round"
          />
          {/* Threshold marker */}
          {threshold && (
            <circle
              cx={config.width / 2 + radius * Math.cos(Math.PI * (1 - threshold))}
              cy={config.height - radius * Math.sin(Math.PI * threshold)}
              r={config.strokeWidth / 3}
              className="fill-muted-foreground"
            />
          )}
        </svg>

        {/* Value arc */}
        <motion.svg
          width={config.width}
          height={config.height}
          className="absolute inset-0 overflow-visible"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          <motion.path
            d={`M ${config.strokeWidth / 2} ${config.height} A ${radius} ${radius} 0 0 1 ${config.width - config.strokeWidth / 2} ${config.height}`}
            fill="none"
            stroke={colors.stroke}
            strokeWidth={config.strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </motion.svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
          {showPercentage && (
            <motion.span
              className={cn('font-bold', config.fontSize, colors.text)}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              {percentage}%
            </motion.span>
          )}
        </div>
      </div>

      {showLabel && (
        <motion.div
          className="mt-2 text-center"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.5 }}
        >
          <span
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium',
              isMatch ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
            )}
          >
            <span className={cn('w-2 h-2 rounded-full', isMatch ? 'bg-green-500' : 'bg-red-500')} />
            {isMatch ? 'Match' : 'No Match'}
          </span>
        </motion.div>
      )}

      {/* Scale labels */}
      <div className="flex justify-between w-full mt-1 px-2 text-xs text-muted-foreground">
        <span>0%</span>
        <span>50%</span>
        <span>100%</span>
      </div>
    </div>
  );
}
