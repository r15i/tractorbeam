## Purpose

Defines the vertical channel of the Tractor Beam reproduction: whether Betaflight's GPS Rescue `RESCUE_ATTAIN_ALT` sanity check accepts or rejects a spoofed altitude feed, classified by the fed climb rate relative to the firmware's own ascend target.

## ADDED Requirements

### Requirement: Sub-rate altitude spoof is rejected
The system SHALL demonstrate that an altitude feed climbing at well below half of the firmware's own ascend rate during `RESCUE_ATTAIN_ALT` is rejected as `RESCUE_STALLED`, with the trigger time logged.

#### Scenario: Static altitude feed
- **WHEN** the reported altitude is held constant (0% of the firmware's ascend rate) throughout `RESCUE_ATTAIN_ALT`
- **THEN** the rescue failure state becomes `RESCUE_STALLED` within the check's failing window, and the trigger time is recorded

#### Scenario: Slow altitude feed
- **WHEN** the reported altitude climbs at roughly 8% of the firmware's ascend rate
- **THEN** the rescue failure state becomes `RESCUE_STALLED` within the check's failing window, and the trigger time is recorded

### Requirement: Rate-matched adaptive altitude spoof is accepted
The system SHALL demonstrate that an altitude feed climbing at or above the firmware's own ascend rate is followed past `RESCUE_ATTAIN_ALT` without tripping `RESCUE_STALLED`.

#### Scenario: Adaptive altitude feed
- **WHEN** the reported altitude climbs at or above 100% of the firmware's ascend rate (e.g. 110%)
- **THEN** the rescue phase advances past `RESCUE_ATTAIN_ALT` (to `RESCUE_PITCH_FORWARD` or later) with no rescue failure flag raised

### Requirement: Near-threshold altitude spoof is characterized as a distribution
The system SHALL support repeated runs of the near-threshold profile so its accept/reject outcome is recorded as a distribution rather than a single point estimate, since the outcome is not deterministic across runs.

#### Scenario: Repeated partial-altitude runs
- **WHEN** the near-threshold profile (climbing at roughly 30% of the firmware's ascend rate) is run multiple times
- **THEN** each run writes a distinct result file and the accept/reject split across runs is captured for comparison

### Requirement: Altitude results are recorded and comparable
The system SHALL log each altitude run's timeline and outcome in a format consistent with the other spoofing channels.

#### Scenario: Run produces a comparable artifact
- **WHEN** an altitude spoofing profile run completes (accepted or rejected)
- **THEN** a CSV is produced recording time, armed state, fed altitude, rescue phase, and rescue failure state, plus a terminal RESULT row with the outcome and trigger time
