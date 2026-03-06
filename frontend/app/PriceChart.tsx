'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchPriceHistory } from './priceCache';

interface PriceRecord {
  tarih: string;
  fiyat: number | null;
  tedavuldeki_pay?: number;
  yatirimci_sayisi?: number;
  portfoy_buyukluk?: number;
}

interface FundSeries {
  found: boolean;
  fund_code: string;
  start_date: string;
  end_date: string;
  total_days: number;
  record_count: number;
  summary: {
    first_price: number | null;
    last_price: number | null;
    min_price: number | null;
    max_price: number | null;
    change_percent: number | null;
  };
  prices: PriceRecord[];
}

interface PriceChartProps {
  fundCodes: string[];      // 1-3 fund codes
  startDate: string;
  endDate: string;
  isDarkMode: boolean;
}

const CHART_HEIGHT = 180;
const CHART_PADDING = { top: 20, right: 16, bottom: 36, left: 58 };
const LINE_COLORS = ['#3b82f6', '#f59e0b', '#ef4444'];  // blue, amber, red
const LINE_COLORS_LIGHT = ['#93c5fd', '#fcd34d', '#fca5a5'];

export default function PriceChart({ fundCodes, startDate, endDate, isDarkMode }: PriceChartProps) {
  const [seriesList, setSeriesList] = useState<FundSeries[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(660);

  const isMulti = fundCodes.length > 1;
  const codesLabel = fundCodes.join(', ');

  // Responsive width
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setChartWidth(Math.floor(entry.contentRect.width));
      }
    });
    ro.observe(el);
    setChartWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Fetch data (with in-memory cache to avoid duplicate calls on remount)
  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchPriceHistory(fundCodes, startDate, endDate);
        if (!cancelled) {
          // Normalize: single fund returns flat, multi returns { funds: [...] }
          if (result.funds) {
            setSeriesList(result.funds.filter((f: FundSeries) => f.found));
          } else {
            setSeriesList(result.found ? [result] : []);
          }
        }
      } catch (err: any) {
        if (!cancelled) setError(err.message || 'Veri alınamadı');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [fundCodes.join(','), startDate, endDate]);

  // Mouse move handler — uses the first (longest) series for X mapping
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!seriesList.length || !svgRef.current) return;
      const maxLen = Math.max(...seriesList.map(s => s.prices.filter(p => p.fiyat != null).length));
      if (maxLen < 2) return;

      const rect = svgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const plotW = chartWidth - CHART_PADDING.left - CHART_PADDING.right;
      const relX = x - CHART_PADDING.left;
      const idx = Math.round((relX / plotW) * (maxLen - 1));
      setHoverIndex(Math.max(0, Math.min(idx, maxLen - 1)));
    },
    [seriesList, chartWidth],
  );

  const handleMouseLeave = useCallback(() => setHoverIndex(null), []);

  // -- Loading --
  if (loading) {
    return (
      <div
        className={`my-3 rounded-lg border p-4 flex items-center justify-center ${isDarkMode ? 'bg-dark-surface border-dark-card' : 'bg-gray-50 border-gray-200'}`}
        style={{ minHeight: 120 }}
      >
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
          <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          <span className={`text-sm ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>
            {codesLabel} fiyat geçmişi yükleniyor...
          </span>
        </div>
      </div>
    );
  }

  // -- Error --
  if (error) {
    return (
      <div className={`my-3 rounded-lg border p-4 text-sm ${isDarkMode ? 'bg-red-900/20 border-red-800 text-red-300' : 'bg-red-50 border-red-200 text-red-700'}`}>
        ⚠️ {codesLabel} fiyat geçmişi alınamadı: {error}
      </div>
    );
  }

  // -- No data --
  if (!seriesList.length) {
    return (
      <div className={`my-3 rounded-lg border p-4 text-sm ${isDarkMode ? 'bg-dark-surface border-dark-card text-dark-muted' : 'bg-gray-50 border-gray-200 text-gray-500'}`}>
        {codesLabel} için seçilen tarih aralığında veri bulunamadı.
      </div>
    );
  }

  // -- Prepare each fund series --
  const prepared = seriesList.map((series, si) => {
    const validPrices = series.prices.filter(p => p.fiyat != null) as (PriceRecord & { fiyat: number })[];
    return { ...series, validPrices, color: LINE_COLORS[si % LINE_COLORS.length], colorLight: LINE_COLORS_LIGHT[si % LINE_COLORS_LIGHT.length] };
  }).filter(s => s.validPrices.length >= 2);

  if (!prepared.length) {
    return (
      <div className={`my-3 rounded-lg border p-4 text-sm ${isDarkMode ? 'bg-dark-surface border-dark-card text-dark-muted' : 'bg-gray-50 border-gray-200 text-gray-500'}`}>
        {codesLabel} için yeterli veri yok (en az 2 fiyat noktası gerekli).
      </div>
    );
  }

  const plotW = chartWidth - CHART_PADDING.left - CHART_PADDING.right;
  const plotH = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom;

  // For single fund: absolute price axis. For multi: normalized % change axis.
  const isSingle = prepared.length === 1;

  // Compute normalized data for each series
  const normalizedSeries = prepared.map(s => {
    const firstPrice = s.validPrices[0].fiyat;
    const normalized = s.validPrices.map(p => ({
      ...p,
      normValue: isSingle ? p.fiyat : ((p.fiyat - firstPrice) / firstPrice) * 100,
    }));
    return { ...s, normalized, firstPrice };
  });

  // Global Y range
  const allNormValues = normalizedSeries.flatMap(s => s.normalized.map(p => p.normValue));
  const minY = Math.min(...allNormValues);
  const maxY = Math.max(...allNormValues);
  const yRange = maxY - minY || 1;
  // Add 5% padding
  const yPadded = yRange * 0.05;
  const yMin = minY - yPadded;
  const yMax = maxY + yPadded;
  const yRangeFinal = yMax - yMin;

  // Longest series determines X count
  const maxPointCount = Math.max(...normalizedSeries.map(s => s.normalized.length));

  const toX = (i: number, total: number) => CHART_PADDING.left + (i / Math.max(total - 1, 1)) * plotW;
  const toY = (val: number) => CHART_PADDING.top + plotH - ((val - yMin) / yRangeFinal) * plotH;

  // Y-axis ticks (5 ticks)
  const yTicks: number[] = [];
  for (let i = 0; i <= 4; i++) {
    yTicks.push(yMin + (yRangeFinal * i) / 4);
  }

  // X-axis labels from the longest series
  const longestSeries = normalizedSeries.reduce((a, b) => a.normalized.length >= b.normalized.length ? a : b);
  const xLabelCount = Math.min(6, longestSeries.normalized.length);
  const xLabels: { index: number; label: string }[] = [];
  for (let i = 0; i < xLabelCount; i++) {
    const idx = Math.round((i / (xLabelCount - 1)) * (longestSeries.normalized.length - 1));
    xLabels.push({ index: idx, label: longestSeries.normalized[idx].tarih });
  }

  // Build paths
  const paths = normalizedSeries.map(s => {
    const d = s.normalized.map((p, i) =>
      `${i === 0 ? 'M' : 'L'}${toX(i, s.normalized.length).toFixed(2)},${toY(p.normValue).toFixed(2)}`
    ).join(' ');
    return { ...s, pathD: d };
  });

  // Area fill only for single fund
  const areaD = isSingle && paths[0]
    ? `${paths[0].pathD} L${toX(paths[0].normalized.length - 1, paths[0].normalized.length).toFixed(2)},${CHART_PADDING.top + plotH} L${toX(0, paths[0].normalized.length).toFixed(2)},${CHART_PADDING.top + plotH} Z`
    : null;

  // For single fund, gradient color based on performance
  const singleChangePct = isSingle ? prepared[0].summary.change_percent : null;
  const singlePositive = singleChangePct != null && singleChangePct >= 0;
  const singleLineColor = isSingle ? (singlePositive ? '#22c55e' : '#ef4444') : '#3b82f6';
  const gradientId = `grad-${fundCodes.join('-')}-${startDate}`.replace(/[^a-zA-Z0-9-]/g, '');

  return (
    <div ref={containerRef} className={`my-3 rounded-lg border overflow-auto relative w-full ${isDarkMode ? 'bg-dark-surface border-dark-card' : 'bg-white border-gray-200'}`}>
      {/* Header */}
      <div className={`px-4 py-2 flex items-center justify-between text-sm border-b ${isDarkMode ? 'border-dark-card' : 'border-gray-100'}`}>
        <div className="flex items-center space-x-2">
          {isSingle ? (
            <>
              <span className="font-semibold">{prepared[0].fund_code}</span>
              <span className={isDarkMode ? 'text-dark-muted' : 'text-gray-500'}>
                {prepared[0].start_date} — {prepared[0].end_date}
              </span>
            </>
          ) : (
            <>
              <span className="font-semibold">Karşılaştırma</span>
              <span className={isDarkMode ? 'text-dark-muted' : 'text-gray-500'}>
                {prepared[0].start_date} — {prepared[0].end_date}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center space-x-3">
          {isSingle && prepared[0].summary.last_price != null && (
            <span className="font-medium">{prepared[0].summary.last_price.toFixed(6)}</span>
          )}
          {isSingle && singleChangePct != null && (
            <span className={`font-semibold text-xs px-1.5 py-0.5 rounded ${singlePositive ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
              {singlePositive ? '▲' : '▼'} %{Math.abs(singleChangePct).toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Legend for multi-fund */}
      {!isSingle && (
        <div className={`px-4 py-1.5 flex items-center space-x-4 text-xs border-b ${isDarkMode ? 'border-dark-card' : 'border-gray-100'}`}>
          {prepared.map((s, i) => {
            const pct = s.summary.change_percent;
            const pos = pct != null && pct >= 0;
            return (
              <div key={s.fund_code} className="flex items-center space-x-1.5">
                <span className="inline-block w-3 h-[3px] rounded-full" style={{ backgroundColor: s.color }}></span>
                <span className="font-semibold">{s.fund_code}</span>
                {pct != null && (
                  <span className={pos ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                    {pos ? '+' : ''}{pct.toFixed(2)}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Tooltip */}
      {hoverIndex != null && (() => {
        // Gather hovered points from each series
        const hoverPoints = paths.map(s => {
          const idx = Math.min(hoverIndex, s.normalized.length - 1);
          const point = s.normalized[idx];
          return point ? { code: s.fund_code, color: s.color, ...point } : null;
        }).filter(Boolean) as Array<{ code: string; color: string; tarih: string; fiyat: number; normValue: number; yatirimci_sayisi?: number; portfoy_buyukluk?: number }>;

        if (!hoverPoints.length) return null;

        const refIdx = Math.min(hoverIndex, longestSeries.normalized.length - 1);
        const dotX = toX(refIdx, longestSeries.normalized.length);
        const tooltipW = 180;
        const flipLeft = dotX + tooltipW + 16 > chartWidth;
        const tooltipLeft = flipLeft ? dotX - tooltipW - 8 : dotX + 12;
        const headerH = isSingle ? 37 : 60;
        const tooltipTop = headerH + CHART_PADDING.top + 4;

        return (
          <div
            className={`absolute z-10 px-3 py-2 rounded-lg shadow-lg text-xs pointer-events-none border ${isDarkMode ? 'bg-dark-card border-dark-card text-dark-text' : 'bg-white border-gray-200 text-gray-800'}`}
            style={{ left: tooltipLeft, top: tooltipTop, minWidth: tooltipW }}
          >
            <div className="font-semibold mb-1">{hoverPoints[0].tarih}</div>
            {hoverPoints.map(hp => (
              <div key={hp.code} className="flex items-center space-x-1.5 py-0.5">
                <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: hp.color }}></span>
                <span className="font-semibold">{hp.code}:</span>
                <span className="font-mono">{hp.fiyat.toFixed(6)}</span>
                {!isSingle && <span className={`${hp.normValue >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>({hp.normValue >= 0 ? '+' : ''}{hp.normValue.toFixed(2)}%)</span>}
              </div>
            ))}
            {isSingle && hoverPoints[0].yatirimci_sayisi != null && (
              <div className="pt-0.5">Yatırımcı: <span className="font-mono">{hoverPoints[0].yatirimci_sayisi.toLocaleString('tr-TR')}</span></div>
            )}
            {isSingle && hoverPoints[0].portfoy_buyukluk != null && (
              <div>Portföy: <span className="font-mono">{(hoverPoints[0].portfoy_buyukluk / 1_000_000).toFixed(1)}M ₺</span></div>
            )}
          </div>
        );
      })()}

      {/* SVG Chart */}
      <svg
        ref={svgRef}
        width={chartWidth}
        height={CHART_HEIGHT}
        className="select-none block"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <defs>
          {isSingle && (
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={singleLineColor} stopOpacity={0.25} />
              <stop offset="100%" stopColor={singleLineColor} stopOpacity={0.02} />
            </linearGradient>
          )}
        </defs>

        {/* Grid lines */}
        {yTicks.map((tick, i) => (
          <line
            key={`grid-${i}`}
            x1={CHART_PADDING.left}
            y1={toY(tick)}
            x2={chartWidth - CHART_PADDING.right}
            y2={toY(tick)}
            stroke={isDarkMode ? '#334155' : '#e5e7eb'}
            strokeWidth={1}
          />
        ))}

        {/* Zero line for multi-fund */}
        {!isSingle && yMin < 0 && yMax > 0 && (
          <line
            x1={CHART_PADDING.left}
            y1={toY(0)}
            x2={chartWidth - CHART_PADDING.right}
            y2={toY(0)}
            stroke={isDarkMode ? '#64748b' : '#9ca3af'}
            strokeWidth={1}
            strokeDasharray="4 2"
          />
        )}

        {/* Area fill (single fund only) */}
        {isSingle && areaD && (
          <path d={areaD} fill={`url(#${gradientId})`} />
        )}

        {/* Price lines */}
        {paths.map((s, si) => (
          <path
            key={s.fund_code}
            d={s.pathD}
            fill="none"
            stroke={isSingle ? singleLineColor : s.color}
            strokeWidth={2}
            strokeLinejoin="round"
          />
        ))}

        {/* Y-axis labels */}
        {yTicks.map((tick, i) => (
          <text
            key={`ytick-${i}`}
            x={CHART_PADDING.left - 6}
            y={toY(tick) + 4}
            textAnchor="end"
            fontSize={10}
            fill={isDarkMode ? '#94a3b8' : '#6b7280'}
          >
            {isSingle
              ? tick.toFixed(tick >= 100 ? 2 : 4)
              : `${tick >= 0 ? '+' : ''}${tick.toFixed(1)}%`}
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map(({ index, label }) => (
          <text
            key={`xtick-${index}`}
            x={toX(index, longestSeries.normalized.length)}
            y={CHART_HEIGHT - 6}
            textAnchor="middle"
            fontSize={10}
            fill={isDarkMode ? '#94a3b8' : '#6b7280'}
          >
            {label.slice(0, 5)}
          </text>
        ))}

        {/* Hover crosshair & dots */}
        {hoverIndex != null && (() => {
          const refIdx = Math.min(hoverIndex, longestSeries.normalized.length - 1);
          const hx = toX(refIdx, longestSeries.normalized.length);
          return (
            <>
              <line
                x1={hx}
                y1={CHART_PADDING.top}
                x2={hx}
                y2={CHART_PADDING.top + plotH}
                stroke={isDarkMode ? '#64748b' : '#9ca3af'}
                strokeWidth={1}
                strokeDasharray="4 2"
              />
              {paths.map(s => {
                const idx = Math.min(hoverIndex, s.normalized.length - 1);
                const point = s.normalized[idx];
                if (!point) return null;
                return (
                  <circle
                    key={`dot-${s.fund_code}`}
                    cx={toX(idx, s.normalized.length)}
                    cy={toY(point.normValue)}
                    r={4}
                    fill={isSingle ? singleLineColor : s.color}
                    stroke={isDarkMode ? '#1e293b' : '#fff'}
                    strokeWidth={2}
                  />
                );
              })}
            </>
          );
        })()}
      </svg>

      {/* Footer stats */}
      <div className={`px-4 py-1.5 text-xs flex items-center justify-between border-t ${isDarkMode ? 'border-dark-card text-dark-muted' : 'border-gray-100 text-gray-500'}`}>
        {isSingle ? (
          <>
            <span>{prepared[0].record_count} gün</span>
            <span>Min: {prepared[0].summary.min_price?.toFixed(4)} — Max: {prepared[0].summary.max_price?.toFixed(4)}</span>
          </>
        ) : (
          <>
            <span>{longestSeries.record_count} gün</span>
            <span>{prepared.length} seri karşılaştırması</span>
          </>
        )}
      </div>
    </div>
  );
}
