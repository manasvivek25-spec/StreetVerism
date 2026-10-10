import { evaluateTouristStatus } from '../utils/statusHelper.ts';

// Vitest-compatible and standalone-executable test suite
function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

export function runLiveModeTests() {
  // Test 1: When coverage is "outside", show outside-coverage message instead of status claim
  {
    const evalResult = evaluateTouristStatus({
      status: 'clear',
      coverage: 'outside',
      mode: 'live',
      weather_available: false,
      is_replay: false,
    });
    assert(evalResult.isOutside === true, 'Expected isOutside to be true');
    assert(
      evalResult.outsideNotice !== undefined &&
        evalResult.outsideNotice.includes('outside the active StreetVerism emergency coverage area'),
      'Expected outside coverage message'
    );
    assert(evalResult.canShowNoKnownHazard === false, 'Must not show positive clear claims when outside');
    assert(evalResult.displayStatus === 'OUTSIDE COVERAGE', 'Expected OUTSIDE COVERAGE display status');
  }

  // Test 2: In live mode when weather_available is false, show neutral notice and never "No known hazard here"
  {
    const evalResult = evaluateTouristStatus({
      status: 'clear',
      coverage: 'covered',
      mode: 'live',
      weather_available: false,
      is_replay: false,
    });
    assert(evalResult.isOutside === false, 'Expected isOutside to be false');
    assert(evalResult.isWeatherUnavailable === true, 'Expected weather unavailable to be true');
    assert(
      evalResult.weatherNotice === 'No live weather data. Follow official guidance.',
      'Expected neutral weather notice'
    );
    assert(
      evalResult.canShowNoKnownHazard === false,
      'Must NEVER show "No known hazard here" when weather is unavailable in live mode'
    );
    assert(evalResult.displayStatus === 'UNASSESSED', 'Expected UNASSESSED status when clear without weather');
  }

  // Test 3: In replay mode with weather present, clear is allowed to show normal assessment
  {
    const evalResult = evaluateTouristStatus({
      status: 'clear',
      coverage: 'covered',
      mode: 'replay',
      weather_available: true,
      is_replay: true,
    });
    assert(evalResult.isWeatherUnavailable === false, 'Expected weather available in replay');
    assert(evalResult.canShowNoKnownHazard === true, 'Expected normal hazard evaluation in replay');
    assert(evalResult.displayStatus === 'CLEAR', 'Expected CLEAR status in replay');
  }
}

runLiveModeTests();
