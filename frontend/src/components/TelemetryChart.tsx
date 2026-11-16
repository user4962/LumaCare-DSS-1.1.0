import type { Telemetry } from '../types'

type Lane = {
  key: 'irradiance_mw_cm2' | 'skin_temperature_c'
  label: string
  unit: string
  color: string
  band?: [number, number]
  limit?: number
  floor: number
  ceiling: number
}

const WIDTH = 760
const LEFT = 56
const RIGHT = 18
const LANE_HEIGHT = 108
const LANE_GAP = 34
const TOP = 22

const niceStep = (span: number, target: number) => {
  const raw = span / target
  const power = 10 ** Math.floor(Math.log10(raw))
  const scaled = raw / power
  const nice = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10
  return nice * power
}

const ticks = (minimum: number, maximum: number, target: number) => {
  const step = niceStep(maximum - minimum, target)
  const values: number[] = []
  for (let value = Math.ceil(minimum / step) * step; value <= maximum + 1e-9; value += step) values.push(Number(value.toFixed(6)))
  return values
}

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}`

/** Two stacked traces with the prescription envelope and the temperature limit. */
export function TelemetryChart({ points, irradianceMin, irradianceMax, temperatureMax }: {
  points: Telemetry[]
  irradianceMin: number
  irradianceMax: number
  temperatureMax: number
}) {
  const irradianceValues = points.map((point) => point.irradiance_mw_cm2)
  const temperatureValues = points.map((point) => point.skin_temperature_c)
  const lanes: Lane[] = [
    {
      key: 'irradiance_mw_cm2', label: 'Irradiance', unit: 'mW/cm²', color: '#1f5a96', band: [irradianceMin, irradianceMax],
      floor: Math.floor(Math.min(irradianceMin, ...irradianceValues) - 1), ceiling: Math.ceil(Math.max(irradianceMax, ...irradianceValues) + 1),
    },
    {
      key: 'skin_temperature_c', label: 'Skin temperature', unit: '°C', color: '#a23a3a', limit: temperatureMax,
      floor: Math.floor(Math.min(35, ...temperatureValues)), ceiling: Math.ceil(Math.max(temperatureMax + 0.5, ...temperatureValues)),
    },
  ]
  const times = points.map((point) => point.elapsed_seconds)
  const start = times.length ? Math.min(...times) : 0
  const end = Math.max(start + 10, ...times)
  const x = (seconds: number) => LEFT + (seconds - start) / (end - start) * (WIDTH - LEFT - RIGHT)
  const height = TOP + lanes.length * LANE_HEIGHT + (lanes.length - 1) * LANE_GAP + 26
  const timeTicks = ticks(start, end, 6)

  return (
    <svg className="telemetry-svg" viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label="Irradiance and skin temperature over elapsed session time">
      {lanes.map((lane, index) => {
        const top = TOP + index * (LANE_HEIGHT + LANE_GAP)
        const y = (value: number) => top + LANE_HEIGHT - (value - lane.floor) / (lane.ceiling - lane.floor) * LANE_HEIGHT
        const path = points.map((point, pointIndex) => `${pointIndex ? 'L' : 'M'}${x(point.elapsed_seconds).toFixed(1)},${y(point[lane.key]).toFixed(1)}`).join(' ')
        return (
          <g key={lane.key}>
            <text x={LEFT} y={top - 8} className="telemetry-svg__lane">{lane.label}, {lane.unit}</text>
            <rect x={LEFT} y={top} width={WIDTH - LEFT - RIGHT} height={LANE_HEIGHT} className="telemetry-svg__frame" />
            {lane.band && <rect x={LEFT} y={y(lane.band[1])} width={WIDTH - LEFT - RIGHT} height={y(lane.band[0]) - y(lane.band[1])} className="telemetry-svg__band" />}
            {ticks(lane.floor, lane.ceiling, 4).map((value) => (
              <g key={value}>
                <line x1={LEFT} x2={WIDTH - RIGHT} y1={y(value)} y2={y(value)} className="telemetry-svg__grid" />
                <text x={LEFT - 8} y={y(value) + 4} textAnchor="end" className="telemetry-svg__tick">{value}</text>
              </g>
            ))}
            {lane.band && lane.band.map((value) => <line key={value} x1={LEFT} x2={WIDTH - RIGHT} y1={y(value)} y2={y(value)} className="telemetry-svg__envelope" />)}
            {lane.limit !== undefined && <>
              <line x1={LEFT} x2={WIDTH - RIGHT} y1={y(lane.limit)} y2={y(lane.limit)} className="telemetry-svg__limit" />
              <text x={WIDTH - RIGHT - 4} y={y(lane.limit) - 5} textAnchor="end" className="telemetry-svg__limit-label">limit {lane.limit} °C</text>
            </>}
            {lane.band && <text x={WIDTH - RIGHT - 4} y={y(lane.band[1]) - 5} textAnchor="end" className="telemetry-svg__band-label">prescription envelope {lane.band[0]}–{lane.band[1]}</text>}
            {points.length > 1 && <path d={path} fill="none" stroke={lane.color} strokeWidth={1.8} strokeLinejoin="round" />}
          </g>
        )
      })}
      {timeTicks.map((value) => <text key={value} x={x(value)} y={height - 6} textAnchor="middle" className="telemetry-svg__tick">{clock(value)}</text>)}
    </svg>
  )
}
