import type { CellStatus } from '../api/types';

export interface StatusEvaluation {
  isOutside: boolean;
  outsideNotice?: string;
  isWeatherUnavailable: boolean;
  weatherNotice?: string;
  canShowNoKnownHazard: boolean;
  displayStatus: string;
}

export function evaluateTouristStatus(params: {
  status: CellStatus;
  coverage?: 'covered' | 'outside';
  mode?: 'live' | 'replay' | 'mock';
  weather_available?: boolean;
  is_replay?: boolean;
}): StatusEvaluation {
  const isOutside = params.coverage === 'outside';
  if (isOutside) {
    return {
      isOutside: true,
      outsideNotice:
        'This location is outside the active StreetVerism emergency coverage area. We cannot provide hazard assessments or verified routes for this location. Please refer to local civil defence guidance.',
      isWeatherUnavailable: false,
      canShowNoKnownHazard: false,
      displayStatus: 'OUTSIDE COVERAGE',
    };
  }

  const isLive = (params.mode === 'live') && !params.is_replay;
  const isWeatherUnavailable = isLive && params.weather_available === false;

  return {
    isOutside: false,
    isWeatherUnavailable,
    weatherNotice: isWeatherUnavailable ? 'No live weather data. Follow official guidance.' : undefined,
    canShowNoKnownHazard: !isWeatherUnavailable,
    displayStatus: isWeatherUnavailable && params.status === 'clear' ? 'UNASSESSED' : params.status.toUpperCase(),
  };
}
