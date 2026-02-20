# EDMC Construction Tracker Plugin

## Overview
An Elite Dangerous Market Connector (EDMC) plugin that tracks construction site material requirements for the System Colonisation feature. It monitors journal events when docking at construction depots, tracks Fleet Carrier cargo, and displays material progress in a tkinter UI within EDMC.

## Project Structure
```
EDMCConstructionTracker/
  load.py                              - Main plugin file (EDMC entry point)
  construction_tracker_data.json       - Persistent data file (auto-generated)
test_plugin.py                         - Unit tests for plugin logic
```

## Key Features
- Tracks multiple construction sites via dropdown selector (station name only, no system)
- Monitors ColonisationConstructionDepot and ColonisationContribution journal events
- Reads Fleet Carrier cargo from FCMaterials.json (Stock field) for CarrierAmount
- Calculates CompletionAmount = RequiredAmount - (ProvidedAmount + CarrierAmount)
- Displays material table with Required, Provided, Carrier, Remaining columns
- Incomplete materials shown in orange; completed materials shown in green
- Updates in real-time as materials are delivered
- Trims $EXT_PANEL_ prefix and trailing semicolons from station names
- Reloads carrier cargo on Docked, Cargo, and CargoTransfer events
- Dark/Light mode toggle with full widget theming (header, labels, button, material table, combobox)
- Persistent data storage across EDMC restarts (construction sites, selected site, dark mode preference)

## Architecture
- **Plugin API**: Uses EDMC plugin_start3, plugin_stop, plugin_app, journal_entry hooks
- **Data Storage**: In-memory dictionary keyed by MarketID, persisted to JSON file in plugin directory
- **Persistence**: construction_tracker_data.json stores construction sites, selected site ID, and dark mode preference; loaded on startup, saved on every state change
- **UI**: tkinter with ttk.Combobox for site selection, grid-based material table, dark/light mode toggle
- **Carrier Tracking**: Reads FCMaterials.json from Elite Dangerous journal directory; uses Items[].Name (cleaned to match resource keys) and Items[].Stock for carrier amounts
- **Material Colors**: Green for fulfilled (completion=0), orange for incomplete (completion>0)

## Recent Changes
- 2026-02-20: Fixed carrier cargo to read from FCMaterials.json instead of Cargo.json
- 2026-02-20: Changed incomplete material text color to orange
- 2026-02-20: Removed system name from dropdown - shows station name only
- 2026-02-20: Fixed dark/light mode button label to show current mode
- 2026-02-20: Added full widget theming - all UI elements follow dark/light mode
- 2026-02-20: Added persistent data storage across EDMC restarts
- 2026-02-20: Initial plugin creation with full MVP feature set

## Testing
Run `python test_plugin.py` to execute all unit tests (17 tests covering core logic, event handling, FCMaterials loading, name trimming, docked event, dark mode, button labels, persistence save/load, and restart persistence).
