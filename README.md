# EDMC Construction Tracker Plugin

An [Elite Dangerous Market Connector (EDMC)](https://github.com/EDCD/EDMarketConnector) plugin that tracks construction site material requirements for the System Colonisation feature in Elite Dangerous.

When a player docks at a construction depot, the plugin monitors journal events to display material requirements, track deliveries, and show completion progress. It supports tracking multiple construction sites, reading Fleet Carrier cargo data via CAPI and FCMaterials.json, and provides a dark/light mode UI.

## Features

- Track material requirements and delivery progress for construction sites
- Support for multiple construction sites via dropdown selector
- Fleet Carrier cargo tracking via CAPI (primary) and FCMaterials.json (fallback)
- Incremental carrier cargo updates from CargoTransfer journal events with sanity checking
- Editable carrier amounts for manual corrections on incomplete materials
- Option to hide completed materials from the display
- Dark/light mode theming (configured in EDMC Settings tab)
- Automatic data persistence across EDMC restarts
- Station name parsing for both game formats

## Installation

1. Download or clone this repository
2. Copy the `EDMCConstructionTracker` folder into your EDMC plugins directory:
   - Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins\`
   - macOS: `~/Library/Application Support/EDMarketConnector/plugins/`
   - Linux: `~/.local/share/EDMarketConnector/plugins/`
3. Restart EDMC

## Requirements

- EDMC (Elite Dangerous Market Connector)
- Python 3.x (provided by EDMC)
- No additional pip dependencies — uses only the Python standard library

## Configuration

Open EDMC Settings and select the **Construction Tracker** tab to configure:
- **Theme**: Light or Dark mode
- **Hide completed materials**: Toggle to hide materials that have been fully delivered

For Fleet Carrier CAPI cargo data, enable "Fleetcarrier CAPI Queries" in EDMC Settings → Configuration.

## How It Works

### Data Sources

The plugin gathers data from three sources:

1. **Journal Events** — EDMC passes game journal events in real-time. The plugin handles:
   - `ColonisationConstructionDepot` — Full material requirements for a site
   - `ColonisationContribution` — Material delivery updates
   - `CargoTransfer` — Carrier cargo transfers (to/from carrier)
   - `Cargo` — Ship inventory updates and transfer validation
   - `Docked`, `Market`, `Location`, `CarrierJump` — Trigger FCMaterials.json reload if modified

2. **CAPI (Frontier Companion API)** — Authoritative Fleet Carrier cargo data, received when the player opens the Carrier Management UI in-game.

3. **FCMaterials.json** — Fallback carrier cargo data read from the game's journal directory. Reloaded on startup and periodically checked for changes every 15 minutes.

### Completion Calculation

```
Remaining = Required - (Provided + Carrier)
```

Materials turn green when fully delivered (remaining = 0 and provided >= required). They stay orange when carrier cargo covers the gap but delivery to the depot is still pending.

### Carrier Cargo Validation

CargoTransfer events are buffered and validated against the next ship Cargo event. If the actual ship inventory change doesn't match the expected transfer amount, the carrier cargo is automatically corrected.

## Plugin Structure

```
EDMCConstructionTracker/
└── load.py          # Main plugin file with all EDMC hooks and logic
test_plugin.py       # Unit tests (46 tests)
```

### EDMC Plugin Hooks

- `plugin_start3(plugin_dir)` — Initialize plugin, load persisted data
- `plugin_stop()` — Cleanup timers, save data
- `plugin_app(parent)` — Build and return the tkinter UI frame
- `plugin_prefs(parent, cmdr, is_beta)` — Settings tab UI
- `prefs_changed(cmdr, is_beta)` — Apply settings changes
- `journal_entry(cmdr, is_beta, system, station, entry, state)` — Process journal events
- `capi_fleetcarrier(data)` — Receive Fleet Carrier CAPI data

## Testing

Run the test suite:

```bash
python test_plugin.py
```

46 tests cover core logic, event handling, CAPI data formats, CargoTransfer tracking, carrier cargo persistence, ship cargo validation, FCMaterials loading, name normalization, station name parsing, UI settings, and data persistence.

## License

This project is provided as-is for the Elite Dangerous community.
