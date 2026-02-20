import json
import os
import sys
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "EDMCConstructionTracker"))

os.environ["DISPLAY"] = ""

try:
    import tkinter as tk
    HAS_TK = True
except (ImportError, RuntimeError):
    HAS_TK = False

import load as plugin


def test_plugin_start():
    result = plugin.plugin_start3("/fake/plugin/dir")
    assert result == "Construction Tracker", f"Expected 'Construction Tracker', got '{result}'"
    print("[PASS] plugin_start3 returns correct name")


def test_construction_depot_processing():
    plugin.carrier_cargo = {"aluminium": 100, "ceramiccomposites": 50}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 12345,
        "ConstructionProgress": 0.45,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 200,
                "Payment": 3239,
            },
            {
                "Name": "$ceramiccomposites_name;",
                "Name_Localised": "Ceramic Composites",
                "RequiredAmount": 300,
                "ProvidedAmount": 100,
                "Payment": 724,
            },
        ],
    }

    plugin._process_construction_depot(entry, "Test Station", "Test System")

    assert 12345 in plugin.construction_sites
    site = plugin.construction_sites[12345]
    assert site["display_name"] == "Test Station - Test System"
    assert site["progress"] == 0.45
    assert len(site["materials"]) == 2

    alum = site["materials"][0]
    assert alum["name"] == "Aluminium"
    assert alum["required"] == 500
    assert alum["provided"] == 200
    assert alum["carrier"] == 100
    assert alum["completion"] == 200  # 500 - (200 + 100) = 200

    ceramic = site["materials"][1]
    assert ceramic["carrier"] == 50
    assert ceramic["completion"] == 150  # 300 - (100 + 50) = 150

    print("[PASS] Construction depot processing with carrier amounts")


def test_multiple_sites():
    plugin.construction_sites.clear()
    plugin.carrier_cargo = {}

    entry1 = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 111,
        "ConstructionProgress": 0.3,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 100,
                "ProvidedAmount": 30,
                "Payment": 1000,
            }
        ],
    }

    entry2 = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 222,
        "ConstructionProgress": 0.7,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 200,
                "ProvidedAmount": 140,
                "Payment": 500,
            }
        ],
    }

    plugin._process_construction_depot(entry1, "Alpha Station", "Alpha System")
    plugin._process_construction_depot(entry2, "Beta Outpost", "Beta System")

    assert len(plugin.construction_sites) == 2
    assert 111 in plugin.construction_sites
    assert 222 in plugin.construction_sites
    assert plugin.construction_sites[111]["display_name"] == "Alpha Station - Alpha System"
    assert plugin.construction_sites[222]["display_name"] == "Beta Outpost - Beta System"
    assert plugin.selected_site_id == 222

    print("[PASS] Multiple construction sites tracked correctly")


def test_completion_amount_calculation():
    assert plugin._calculate_completion(500, 200, 100) == 200
    assert plugin._calculate_completion(500, 400, 100) == 0
    assert plugin._calculate_completion(500, 300, 300) == 0
    assert plugin._calculate_completion(100, 0, 0) == 100
    assert plugin._calculate_completion(100, 100, 0) == 0
    assert plugin._calculate_completion(100, 50, 50) == 0
    assert plugin._calculate_completion(100, 80, 30) == 0

    print("[PASS] CompletionAmount calculation (never goes negative)")


def test_carrier_cargo_update():
    plugin.construction_sites.clear()
    plugin.carrier_cargo = {"aluminium": 0}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 999,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 200,
                "ProvidedAmount": 50,
                "Payment": 1000,
            }
        ],
    }
    plugin._process_construction_depot(entry, "Test", "System")

    assert plugin.construction_sites[999]["materials"][0]["completion"] == 150

    plugin.carrier_cargo = {"aluminium": 80}
    plugin._update_carrier_amounts()

    mat = plugin.construction_sites[999]["materials"][0]
    assert mat["carrier"] == 80
    assert mat["completion"] == 70  # 200 - (50 + 80) = 70

    print("[PASS] Carrier cargo update recalculates CompletionAmount")


def test_contribution_updates():
    plugin.construction_sites.clear()
    plugin.carrier_cargo = {"aluminium": 50}

    depot_entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 555,
        "ConstructionProgress": 0.2,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 400,
                "ProvidedAmount": 80,
                "Payment": 1000,
            }
        ],
    }
    plugin._process_construction_depot(depot_entry, "Depot", "System")

    mat = plugin.construction_sites[555]["materials"][0]
    assert mat["provided"] == 80
    assert mat["completion"] == 270  # 400 - (80 + 50)

    contrib_entry = {
        "event": "ColonisationContribution",
        "MarketID": 555,
        "Contributions": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "Amount": 20,
            }
        ],
    }

    state = {"JournalDir": "/fake"}
    plugin.journal_entry("Cmdr", False, "System", "Depot", contrib_entry, state)

    mat = plugin.construction_sites[555]["materials"][0]
    assert mat["provided"] == 100
    assert mat["completion"] == 250  # 400 - (100 + 50)

    print("[PASS] ColonisationContribution updates ProvidedAmount and recalculates CompletionAmount")


def test_cargo_json_loading():
    with tempfile.TemporaryDirectory() as tmpdir:
        cargo_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "Cargo",
            "Vessel": "Ship",
            "Count": 3,
            "Inventory": [
                {"Name": "aluminium", "Count": 120, "Stolen": 0},
                {"Name": "steel", "Count": 80, "Stolen": 0},
                {"Name": "polymers", "Count": 45, "Stolen": 0},
            ],
        }
        with open(os.path.join(tmpdir, "Cargo.json"), "w") as f:
            json.dump(cargo_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()
        plugin._load_carrier_cargo()

        assert plugin.carrier_cargo.get("aluminium") == 120
        assert plugin.carrier_cargo.get("steel") == 80
        assert plugin.carrier_cargo.get("polymers") == 45

    print("[PASS] Cargo.json loading works correctly")


def test_display_name_generation():
    assert plugin._get_site_display_name("Station", "System", 1) == "Station - System"
    assert plugin._get_site_display_name("Station", None, 1) == "Station"
    assert plugin._get_site_display_name(None, "System", 1) == "System"
    assert plugin._get_site_display_name(None, None, 42) == "Site #42"

    print("[PASS] Display name generation")


def test_clean_station_name():
    assert plugin._clean_station_name("$EXT_PANEL_ColDepot;") == "ColDepot"
    assert plugin._clean_station_name("$EXT_PANEL_MyStation;") == "MyStation"
    assert plugin._clean_station_name("$EXT_PANEL_Test") == "Test"
    assert plugin._clean_station_name("Normal Station") == "Normal Station"
    assert plugin._clean_station_name("$EXT_PANEL_") == ""

    print("[PASS] Station name $EXT_PANEL_ trimming")


def test_display_name_with_ext_panel():
    plugin.construction_sites.clear()
    plugin.carrier_cargo = {}

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 777,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [],
    }
    plugin._process_construction_depot(entry, "$EXT_PANEL_ColDepot;", "Sol")
    assert plugin.construction_sites[777]["display_name"] == "ColDepot - Sol"

    print("[PASS] Display name trims $EXT_PANEL_ prefix from station name")


def test_docked_event_loads_carrier_cargo():
    with tempfile.TemporaryDirectory() as tmpdir:
        cargo_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "Cargo",
            "Vessel": "Ship",
            "Count": 2,
            "Inventory": [
                {"Name": "aluminium", "Count": 200, "Stolen": 0},
                {"Name": "steel", "Count": 150, "Stolen": 0},
            ],
        }
        with open(os.path.join(tmpdir, "Cargo.json"), "w") as f:
            json.dump(cargo_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()

        docked_entry = {
            "event": "Docked",
            "StationName": "Test Station",
            "StarSystem": "Test System",
            "MarketID": 99999,
        }
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Test System", "Test Station", docked_entry, state)

        assert plugin.carrier_cargo.get("aluminium") == 200
        assert plugin.carrier_cargo.get("steel") == 150

    print("[PASS] Docked event triggers carrier cargo reload")


def test_dark_mode_toggle():
    assert plugin.dark_mode is False or plugin.dark_mode is True
    original = plugin.dark_mode
    plugin.dark_mode = False
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is True
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is False
    plugin.dark_mode = original

    print("[PASS] Dark mode toggle switches state")


def test_journal_entry_cargo_event():
    with tempfile.TemporaryDirectory() as tmpdir:
        cargo_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "Cargo",
            "Vessel": "Ship",
            "Count": 1,
            "Inventory": [
                {"Name": "gold", "Count": 50, "Stolen": 0},
            ],
        }
        with open(os.path.join(tmpdir, "Cargo.json"), "w") as f:
            json.dump(cargo_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()

        cargo_entry = {"event": "Cargo", "Vessel": "Ship", "Count": 1}
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

        assert plugin.carrier_cargo.get("gold") == 50

    print("[PASS] journal_entry handles Cargo event")


if __name__ == "__main__":
    print("Running Construction Tracker Plugin Tests\n")

    test_plugin_start()
    test_completion_amount_calculation()
    test_display_name_generation()
    test_clean_station_name()
    test_display_name_with_ext_panel()
    test_construction_depot_processing()
    test_multiple_sites()
    test_carrier_cargo_update()
    test_contribution_updates()
    test_cargo_json_loading()
    test_journal_entry_cargo_event()
    test_docked_event_loads_carrier_cargo()
    test_dark_mode_toggle()

    print(f"\nAll tests passed!")
