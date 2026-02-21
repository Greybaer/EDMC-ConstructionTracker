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

_test_tmpdir = tempfile.mkdtemp()


def _reset_plugin():
    plugin.construction_sites.clear()
    plugin.carrier_cargo.clear()
    plugin.selected_site_id = None
    plugin.dark_mode = False
    plugin.plugin_dir = _test_tmpdir
    save_path = os.path.join(_test_tmpdir, plugin.SAVE_FILE)
    if os.path.exists(save_path):
        os.remove(save_path)


def test_plugin_start():
    result = plugin.plugin_start3(_test_tmpdir)
    assert result == "Construction Tracker", f"Expected 'Construction Tracker', got '{result}'"
    print("[PASS] plugin_start3 returns correct name")


def test_construction_depot_processing():
    _reset_plugin()
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
    assert site["display_name"] == "Test Station"
    assert site["progress"] == 0.45
    assert len(site["materials"]) == 2

    alum = site["materials"][0]
    assert alum["name"] == "Aluminium"
    assert alum["required"] == 500
    assert alum["provided"] == 200
    assert alum["carrier"] == 100
    assert alum["completion"] == 200

    ceramic = site["materials"][1]
    assert ceramic["carrier"] == 50
    assert ceramic["completion"] == 150

    print("[PASS] Construction depot processing with carrier amounts")


def test_multiple_sites():
    _reset_plugin()

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
    assert plugin.construction_sites[111]["display_name"] == "Alpha Station"
    assert plugin.construction_sites[222]["display_name"] == "Beta Outpost"
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
    _reset_plugin()
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
    assert mat["completion"] == 70

    print("[PASS] Carrier cargo update recalculates CompletionAmount")


def test_contribution_updates():
    _reset_plugin()
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
    assert mat["completion"] == 270

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
    assert mat["completion"] == 250

    print("[PASS] ColonisationContribution updates ProvidedAmount and recalculates CompletionAmount")


def test_fc_materials_loading():
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "MarketID": 3700005632,
            "CarrierName": "TEST CARRIER",
            "CarrierID": "T7T-TTT",
            "Items": [
                {"id": 1, "Name": "$aluminium_name;", "Name_Localised": "Aluminium",
                 "Stock": 120, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 2, "Name": "$steel_name;", "Name_Localised": "Steel",
                 "Stock": 80, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 3, "Name": "$polymers_name;", "Name_Localised": "Polymers",
                 "Stock": 45, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 4, "Name": "$gold_name;", "Name_Localised": "Gold",
                 "Stock": 0, "Demand": 100, "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()
        plugin._load_carrier_cargo()

        assert plugin.carrier_cargo.get("aluminium") == 120
        assert plugin.carrier_cargo.get("steel") == 80
        assert plugin.carrier_cargo.get("polymers") == 45
        assert plugin.carrier_cargo.get("gold", 0) == 0

    print("[PASS] FCMaterials.json loading works correctly")


def test_display_name_generation():
    assert plugin._get_site_display_name("Station", "System", 1) == "Station"
    assert plugin._get_site_display_name("Station", None, 1) == "Station"
    assert plugin._get_site_display_name(None, "System", 1) == "Site #1"
    assert plugin._get_site_display_name(None, None, 42) == "Site #42"

    print("[PASS] Display name generation")


def test_normalize_name():
    assert plugin._normalize_name("$aluminium_name;") == "aluminium"
    assert plugin._normalize_name("$steel_name;") == "steel"
    assert plugin._normalize_name("Steel") == "steel"
    assert plugin._normalize_name("steel") == "steel"
    assert plugin._normalize_name("$polymers_name;") == "polymers"
    assert plugin._normalize_name("polymers") == "polymers"
    assert plugin._normalize_name("$ceramiccomposites_name;") == "ceramiccomposites"
    assert plugin._normalize_name("  $Gold_Name;  ") == "gold"
    assert plugin._normalize_name("") == ""

    print("[PASS] Name normalization handles all formats")


def test_parse_station_name():
    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_ColDepot;My Station - Sol;")
    assert site_type == "ColDepot", f"Expected 'ColDepot', got '{site_type}'"
    assert site_name == "My Station", f"Expected 'My Station', got '{site_name}'"
    assert system_name == "Sol", f"Expected 'Sol', got '{system_name}'"

    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_Hub;Alpha Base - Barnard's Star;")
    assert site_type == "Hub"
    assert site_name == "Alpha Base"
    assert system_name == "Barnard's Star"

    site_type, site_name, system_name = plugin._parse_station_name("Normal Station")
    assert site_type == ""
    assert site_name == "Normal Station"
    assert system_name == ""

    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_ColDepot;")
    assert site_type == ""
    assert site_name == "ColDepot"
    assert system_name == ""

    site_type, site_name, system_name = plugin._parse_station_name("$EXT_PANEL_Outpost;My Outpost - Alpha Centauri;")
    assert site_type == "Outpost"
    assert site_name == "My Outpost"
    assert system_name == "Alpha Centauri"

    print("[PASS] Station name parsing into site type, site, and system")


def test_display_name_with_ext_panel():
    _reset_plugin()

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 777,
        "ConstructionProgress": 0.5,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [],
    }
    plugin._process_construction_depot(entry, "$EXT_PANEL_ColDepot;My Station - Sol;", "Sol")
    assert plugin.construction_sites[777]["display_name"] == "My Station"
    assert plugin.construction_sites[777]["site_type"] == "ColDepot"
    assert plugin.construction_sites[777]["site_name"] == "My Station"
    assert plugin.construction_sites[777]["parsed_system"] == "Sol"

    print("[PASS] Display name extracts site name from $EXT_PANEL_ format")


def test_docked_event_loads_carrier_cargo():
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "MarketID": 3700005632,
            "CarrierName": "TEST CARRIER",
            "CarrierID": "T7T-TTT",
            "Items": [
                {"id": 1, "Name": "$aluminium_name;", "Name_Localised": "Aluminium",
                 "Stock": 200, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
                {"id": 2, "Name": "$steel_name;", "Name_Localised": "Steel",
                 "Stock": 150, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

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


def test_market_event_loads_carrier_cargo():
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "Items": [
                {"id": 1, "Name": "steel", "Name_Localised": "Steel",
                 "Stock": 300, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()

        market_entry = {"event": "Market", "MarketID": 99999, "StationName": "Test"}
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Sys", "Stn", market_entry, state)

        assert plugin.carrier_cargo.get("steel") == 300

    print("[PASS] Market event triggers carrier cargo reload")


def test_capi_fleetcarrier_cargo_list_format():
    _reset_plugin()

    depot_entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 6000,
        "ConstructionProgress": 0.1,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 100,
                "Payment": 1000,
            },
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 300,
                "ProvidedAmount": 50,
                "Payment": 500,
            },
        ],
    }
    plugin._process_construction_depot(depot_entry, "Test Station", "Test System")

    capi_data = {
        "name": {"callsign": "T3S-T0P", "name": "TEST CARRIER"},
        "currentStarSystem": "Sol",
        "cargo": [
            {"commodity": "Aluminium", "quantity": 200},
            {"commodity": "Steel", "quantity": 150},
        ],
        "orders": {"commodities": {"sales": {}, "purchases": {}}},
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200
    assert plugin.carrier_cargo.get("steel") == 150

    mat_alum = plugin.construction_sites[6000]["materials"][0]
    assert mat_alum["carrier"] == 200
    assert mat_alum["completion"] == 200

    mat_steel = plugin.construction_sites[6000]["materials"][1]
    assert mat_steel["carrier"] == 150
    assert mat_steel["completion"] == 100

    print("[PASS] CAPI fleetcarrier cargo list format populates carrier amounts")


def test_capi_fleetcarrier_cargo_dict_format():
    _reset_plugin()

    capi_data = {
        "cargo": {
            "capacity": 25000,
            "qty": 200,
            "commodities": [
                {"name": "Aluminium", "qty": 200},
            ],
        },
        "orders": {"commodities": {"sales": {}, "purchases": {}}},
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200

    print("[PASS] CAPI fleetcarrier cargo dict format fallback works")


def test_capi_fleetcarrier_cargo_duplicate_entries():
    _reset_plugin()

    capi_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": 200},
            {"commodity": "Aluminium", "quantity": 100},
            {"commodity": "Steel", "quantity": 50},
        ],
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 300
    assert plugin.carrier_cargo.get("steel") == 50

    print("[PASS] CAPI fleetcarrier sums duplicate cargo entries")


def test_capi_fleetcarrier_sales_orders():
    _reset_plugin()

    capi_data = {
        "cargo": [],
        "orders": {
            "commodities": {
                "sales": {
                    "100": {"id": 128049204, "name": "Gold", "outstanding": 500, "price": 9500, "total": 1000, "blackMarket": False},
                    "101": {"id": 128049168, "name": "Aluminium", "outstanding": 300, "price": 340, "total": 500, "blackMarket": False},
                },
                "purchases": {},
            }
        },
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("gold") == 500
    assert plugin.carrier_cargo.get("aluminium") == 300

    print("[PASS] CAPI fleetcarrier sales orders populate carrier amounts")


def test_capi_fleetcarrier_string_values():
    _reset_plugin()

    capi_data = {
        "cargo": [
            {"commodity": "Aluminium", "quantity": "200"},
            {"commodity": "Steel", "quantity": "150"},
        ],
        "orders": {
            "commodities": {
                "sales": {
                    "100": {"name": "Gold", "outstanding": "500"},
                },
                "purchases": {},
            }
        },
    }
    plugin.capi_fleetcarrier(capi_data)

    assert plugin.carrier_cargo.get("aluminium") == 200
    assert plugin.carrier_cargo.get("steel") == 150
    assert plugin.carrier_cargo.get("gold") == 500

    print("[PASS] CAPI fleetcarrier handles string quantity values")


def test_capi_fleetcarrier_empty_data():
    _reset_plugin()
    plugin.carrier_cargo = {"old_item": 100}

    plugin.capi_fleetcarrier(None)
    assert plugin.carrier_cargo.get("old_item") == 100

    capi_data = {"cargo": [], "orders": {"commodities": {"sales": {}, "purchases": {}}}}
    plugin.capi_fleetcarrier(capi_data)
    assert len(plugin.carrier_cargo) == 0

    print("[PASS] CAPI fleetcarrier handles empty/null data")


def test_dark_mode_toggle():
    _reset_plugin()
    plugin.dark_mode = False
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is True
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is False

    print("[PASS] Dark mode toggle switches state")


def test_dark_mode_button_label():
    _reset_plugin()
    plugin.dark_mode = False
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is True
    if plugin.dark_mode_btn:
        assert plugin.dark_mode_btn.cget("text") == "Dark"
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is False
    if plugin.dark_mode_btn:
        assert plugin.dark_mode_btn.cget("text") == "Light"

    print("[PASS] Dark mode button label shows current mode")


def test_journal_entry_cargo_event():
    with tempfile.TemporaryDirectory() as tmpdir:
        fc_data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "event": "FCMaterials",
            "MarketID": 3700005632,
            "CarrierName": "TEST CARRIER",
            "CarrierID": "T7T-TTT",
            "Items": [
                {"id": 1, "Name": "$gold_name;", "Name_Localised": "Gold",
                 "Stock": 50, "Demand": 0, "BuyPrice": 0, "SellPrice": 0},
            ],
        }
        with open(os.path.join(tmpdir, "FCMaterials.json"), "w") as f:
            json.dump(fc_data, f)

        plugin.journal_dir = tmpdir
        plugin.carrier_cargo.clear()

        cargo_entry = {"event": "Cargo", "Vessel": "Ship", "Count": 1}
        state = {"JournalDir": tmpdir}
        plugin.journal_entry("Cmdr", False, "Sys", "Stn", cargo_entry, state)

        assert plugin.carrier_cargo.get("gold") == 50

    print("[PASS] journal_entry handles Cargo event")


def test_save_and_load_data():
    _reset_plugin()
    plugin.carrier_cargo = {"aluminium": 100}
    plugin.dark_mode = True

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 8888,
        "ConstructionProgress": 0.6,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$aluminium_name;",
                "Name_Localised": "Aluminium",
                "RequiredAmount": 500,
                "ProvidedAmount": 200,
                "Payment": 1000,
            }
        ],
    }
    plugin._process_construction_depot(entry, "Persist Station", "Persist System")

    save_path = os.path.join(_test_tmpdir, plugin.SAVE_FILE)
    assert os.path.exists(save_path), "Save file should exist after processing depot"

    with open(save_path, "r") as f:
        saved = json.load(f)
    assert saved["dark_mode"] is True
    assert saved["selected_site_id"] == 8888
    assert "8888" in saved["construction_sites"]
    assert saved["construction_sites"]["8888"]["display_name"] == "Persist Station"

    plugin.construction_sites.clear()
    plugin.selected_site_id = None
    plugin.dark_mode = False

    plugin._load_data()

    assert plugin.dark_mode is True
    assert plugin.selected_site_id == 8888
    assert 8888 in plugin.construction_sites
    site = plugin.construction_sites[8888]
    assert site["display_name"] == "Persist Station"
    assert site["progress"] == 0.6
    assert len(site["materials"]) == 1
    assert site["materials"][0]["name"] == "Aluminium"
    assert site["materials"][0]["required"] == 500
    assert site["materials"][0]["provided"] == 200

    print("[PASS] Data persistence: save and load works correctly")


def test_persistence_across_restart():
    _reset_plugin()
    plugin.carrier_cargo = {"steel": 75}
    plugin.dark_mode = True

    entry = {
        "event": "ColonisationConstructionDepot",
        "MarketID": 4444,
        "ConstructionProgress": 0.3,
        "ConstructionComplete": False,
        "ConstructionFailed": False,
        "ResourcesRequired": [
            {
                "Name": "$steel_name;",
                "Name_Localised": "Steel",
                "RequiredAmount": 300,
                "ProvidedAmount": 100,
                "Payment": 500,
            }
        ],
    }
    plugin._process_construction_depot(entry, "Restart Station", "Restart System")

    plugin.plugin_stop()

    plugin.construction_sites.clear()
    plugin.selected_site_id = None
    plugin.dark_mode = False

    result = plugin.plugin_start3(_test_tmpdir)
    assert result == "Construction Tracker"

    assert plugin.dark_mode is True
    assert plugin.selected_site_id == 4444
    assert 4444 in plugin.construction_sites
    site = plugin.construction_sites[4444]
    assert site["display_name"] == "Restart Station"

    print("[PASS] Data persists across plugin stop/start cycle")


def test_dark_mode_preference_saved():
    _reset_plugin()
    plugin.dark_mode = False
    plugin._toggle_dark_mode()
    assert plugin.dark_mode is True

    save_path = os.path.join(_test_tmpdir, plugin.SAVE_FILE)
    assert os.path.exists(save_path)
    with open(save_path, "r") as f:
        saved = json.load(f)
    assert saved["dark_mode"] is True

    plugin._toggle_dark_mode()
    with open(save_path, "r") as f:
        saved = json.load(f)
    assert saved["dark_mode"] is False

    print("[PASS] Dark mode preference is saved on toggle")


if __name__ == "__main__":
    print("Running Construction Tracker Plugin Tests\n")

    test_plugin_start()
    test_completion_amount_calculation()
    test_display_name_generation()
    test_normalize_name()
    test_parse_station_name()
    test_display_name_with_ext_panel()
    test_construction_depot_processing()
    test_multiple_sites()
    test_carrier_cargo_update()
    test_contribution_updates()
    test_fc_materials_loading()
    test_journal_entry_cargo_event()
    test_docked_event_loads_carrier_cargo()
    test_market_event_loads_carrier_cargo()
    test_capi_fleetcarrier_cargo_list_format()
    test_capi_fleetcarrier_cargo_dict_format()
    test_capi_fleetcarrier_cargo_duplicate_entries()
    test_capi_fleetcarrier_sales_orders()
    test_capi_fleetcarrier_string_values()
    test_capi_fleetcarrier_empty_data()
    test_dark_mode_toggle()
    test_dark_mode_button_label()
    test_save_and_load_data()
    test_persistence_across_restart()
    test_dark_mode_preference_saved()

    print(f"\nAll tests passed!")
