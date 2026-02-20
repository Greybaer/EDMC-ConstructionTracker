from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import tkinter as tk
    from tkinter import ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None
    ttk = None

plugin_name = "Construction Tracker"
plugin_version = "1.1.0"

logger = logging.getLogger(f"{plugin_name}")

carrier_cargo: Dict[str, int] = {}
construction_sites: Dict[int, Dict[str, Any]] = {}
selected_site_id: Optional[int] = None
journal_dir: Optional[str] = None
plugin_dir: Optional[str] = None
dark_mode: bool = False

frame = None
site_selector = None
site_var = None
progress_var = None
material_frame = None
status_var = None
dark_mode_btn = None
header_label = None
site_label = None
progress_label_widget = None
status_label_widget = None

DARK_BG = "#1e1e1e"
DARK_FG = "#d4d4d4"
DARK_HEADER_FG = "#ffffff"
DARK_GREEN = "#4ec94e"
DARK_ORANGE = "#ff8c00"
DARK_STATUS_FG = "#888888"
DARK_BTN_BG = "#333333"
LIGHT_BG = "SystemButtonFace"
LIGHT_FG = "black"
LIGHT_GREEN = "green"
LIGHT_ORANGE = "#e67300"
LIGHT_STATUS_FG = "gray"

SAVE_FILE = "construction_tracker_data.json"


def _get_save_path() -> Optional[str]:
    if plugin_dir:
        return os.path.join(plugin_dir, SAVE_FILE)
    return None


def _save_data() -> None:
    path = _get_save_path()
    if not path:
        return
    try:
        save_obj = {
            "dark_mode": dark_mode,
            "selected_site_id": selected_site_id,
            "construction_sites": {str(k): v for k, v in construction_sites.items()},
        }
        with open(path, "w") as f:
            json.dump(save_obj, f, indent=2)
        logger.debug(f"Saved data to {path}")
    except Exception as e:
        logger.error(f"Error saving data: {e}")


def _load_data() -> None:
    global dark_mode, selected_site_id, construction_sites
    path = _get_save_path()
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r") as f:
            save_obj = json.load(f)
        dark_mode = save_obj.get("dark_mode", False)
        selected_site_id = save_obj.get("selected_site_id")
        raw_sites = save_obj.get("construction_sites", {})
        construction_sites.clear()
        for k, v in raw_sites.items():
            construction_sites[int(k)] = v
        logger.info(f"Loaded {len(construction_sites)} construction sites from save")
    except Exception as e:
        logger.error(f"Error loading data: {e}")


def plugin_start3(plugin_dir_path: str) -> str:
    global plugin_dir
    plugin_dir = plugin_dir_path
    _load_data()
    logger.info(f"{plugin_name} v{plugin_version} started")
    return plugin_name


def plugin_stop() -> None:
    _save_data()
    logger.info(f"{plugin_name} stopped")


def plugin_app(parent: tk.Frame) -> tk.Frame:
    global frame, site_selector, site_var, progress_var, material_frame, status_var
    global dark_mode_btn, header_label, site_label, progress_label_widget, status_label_widget

    frame = tk.Frame(parent)

    header_label = tk.Label(frame, text="Construction Tracker", font=("Helvetica", 10, "bold"))
    header_label.grid(row=0, column=0, columnspan=1, sticky=tk.W, pady=(0, 4))

    dark_mode_btn = tk.Button(frame, text="Dark" if dark_mode else "Light",
                               font=("Helvetica", 7), command=_toggle_dark_mode, width=4)
    dark_mode_btn.grid(row=0, column=2, sticky=tk.E, pady=(0, 4), padx=(4, 0))

    site_label = tk.Label(frame, text="Site:")
    site_label.grid(row=1, column=0, sticky=tk.W)
    site_var = tk.StringVar(value="No sites tracked")
    site_selector = ttk.Combobox(frame, textvariable=site_var, state="readonly", width=35)
    site_selector.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=(4, 0))
    site_selector.bind("<<ComboboxSelected>>", _on_site_selected)

    progress_var = tk.StringVar(value="Progress: --")
    progress_label_widget = tk.Label(frame, textvariable=progress_var, font=("Helvetica", 9))
    progress_label_widget.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(4, 2))

    status_var = tk.StringVar(value="Waiting for construction site data...")
    status_label_widget = tk.Label(frame, textvariable=status_var, font=("Helvetica", 8), fg="gray")
    status_label_widget.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))

    material_frame = tk.Frame(frame)
    material_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W)

    _apply_theme()

    if construction_sites:
        _update_site_selector()
        _update_display()

    return frame


def _on_site_selected(event=None) -> None:
    global selected_site_id
    if not site_var or not construction_sites:
        return

    selected_name = site_var.get()
    for mid, site_data in construction_sites.items():
        if site_data["display_name"] == selected_name:
            selected_site_id = mid
            _update_display()
            _save_data()
            return


def _clean_station_name(name: str) -> str:
    if name.startswith("$EXT_PANEL_"):
        name = name[len("$EXT_PANEL_"):]
    if name.endswith(";"):
        name = name[:-1]
    return name


def _get_site_display_name(station: Optional[str], system: Optional[str], market_id: int) -> str:
    if station:
        return _clean_station_name(station)
    return f"Site #{market_id}"


def _load_carrier_cargo() -> None:
    global carrier_cargo
    if not journal_dir:
        return

    fc_path = os.path.join(journal_dir, "FCMaterials.json")
    if not os.path.exists(fc_path):
        return

    try:
        with open(fc_path, "r") as f:
            data = json.load(f)

        items = data.get("Items", [])
        carrier_cargo.clear()
        for item in items:
            raw_name = item.get("Name", "")
            name_key = raw_name.replace("$", "").replace("_name;", "").lower()
            stock = item.get("Stock", 0)
            if name_key and stock > 0:
                carrier_cargo[name_key] = stock
        logger.debug(f"Loaded FC cargo: {len(carrier_cargo)} items from FCMaterials.json")
    except Exception as e:
        logger.error(f"Error loading FCMaterials.json: {e}")


def _calculate_completion(required: int, provided: int, carrier: int) -> int:
    remaining = required - (provided + carrier)
    return max(0, remaining)


def _process_construction_depot(entry: Dict[str, Any], station: Optional[str], system: Optional[str]) -> None:
    global selected_site_id

    market_id = entry.get("MarketID")
    if market_id is None:
        return

    progress = entry.get("ConstructionProgress", 0.0)
    complete = entry.get("ConstructionComplete", False)
    failed = entry.get("ConstructionFailed", False)
    resources = entry.get("ResourcesRequired", [])

    display_name = _get_site_display_name(station, system, market_id)

    materials: List[Dict[str, Any]] = []
    for res in resources:
        raw_name = res.get("Name", "")
        name_localised = res.get("Name_Localised", raw_name)
        name_key = raw_name.replace("$", "").replace("_name;", "").lower()
        required_amount = res.get("RequiredAmount", 0)
        provided_amount = res.get("ProvidedAmount", 0)
        carrier_amount = carrier_cargo.get(name_key, 0)
        completion_amount = _calculate_completion(required_amount, provided_amount, carrier_amount)

        materials.append({
            "name": name_localised,
            "name_key": name_key,
            "required": required_amount,
            "provided": provided_amount,
            "carrier": carrier_amount,
            "completion": completion_amount,
        })

    construction_sites[market_id] = {
        "display_name": display_name,
        "market_id": market_id,
        "progress": progress,
        "complete": complete,
        "failed": failed,
        "materials": materials,
        "station": station,
        "system": system,
    }

    selected_site_id = market_id

    _update_site_selector()
    _update_display()
    _save_data()
    logger.info(f"Processed construction depot: {display_name} ({progress:.1%})")


def _update_carrier_amounts() -> None:
    for mid, site_data in construction_sites.items():
        for mat in site_data["materials"]:
            carrier_amount = carrier_cargo.get(mat["name_key"], 0)
            mat["carrier"] = carrier_amount
            mat["completion"] = _calculate_completion(mat["required"], mat["provided"], carrier_amount)


def _update_site_selector() -> None:
    if not site_selector or not site_var:
        return

    names = [site["display_name"] for site in construction_sites.values()]
    site_selector["values"] = names

    if selected_site_id and selected_site_id in construction_sites:
        site_var.set(construction_sites[selected_site_id]["display_name"])
    elif names:
        site_var.set(names[0])


def _update_display() -> None:
    if not progress_var or not material_frame or not status_var:
        return

    if not selected_site_id or selected_site_id not in construction_sites:
        progress_var.set("Progress: --")
        status_var.set("Waiting for construction site data...")
        _clear_material_display()
        return

    site_data = construction_sites[selected_site_id]
    progress = site_data["progress"]

    if site_data["complete"]:
        progress_var.set(f"Progress: COMPLETE")
        status_var.set("Construction finished!")
    elif site_data["failed"]:
        progress_var.set(f"Progress: FAILED")
        status_var.set("Construction failed.")
    else:
        progress_var.set(f"Progress: {progress:.1%}")
        total_materials = len(site_data["materials"])
        completed_materials = sum(1 for m in site_data["materials"] if m["completion"] == 0)
        status_var.set(f"{completed_materials}/{total_materials} materials fulfilled")

    _render_materials(site_data["materials"])


def _clear_material_display() -> None:
    if not material_frame:
        return
    for widget in material_frame.winfo_children():
        widget.destroy()


def _toggle_dark_mode() -> None:
    global dark_mode
    dark_mode = not dark_mode
    if dark_mode_btn:
        dark_mode_btn.config(text="Dark" if dark_mode else "Light")
    _apply_theme()
    _update_display()
    _save_data()


def _apply_theme() -> None:
    if not frame:
        return

    bg = DARK_BG if dark_mode else LIGHT_BG
    fg = DARK_FG if dark_mode else LIGHT_FG
    header_fg = DARK_HEADER_FG if dark_mode else LIGHT_FG
    status_fg = DARK_STATUS_FG if dark_mode else LIGHT_STATUS_FG
    btn_bg = DARK_BTN_BG if dark_mode else LIGHT_BG

    frame.config(bg=bg)

    if header_label:
        header_label.config(bg=bg, fg=header_fg)

    if site_label:
        site_label.config(bg=bg, fg=fg)

    if progress_label_widget:
        progress_label_widget.config(bg=bg, fg=fg)

    if status_label_widget:
        status_label_widget.config(bg=bg, fg=status_fg)

    if dark_mode_btn:
        dark_mode_btn.config(bg=btn_bg, fg=fg)

    if material_frame:
        material_frame.config(bg=bg)

    if site_selector and HAS_TK:
        try:
            style = ttk.Style()
            style.map("TCombobox",
                      fieldbackground=[("readonly", bg)],
                      foreground=[("readonly", fg)],
                      selectbackground=[("readonly", bg)],
                      selectforeground=[("readonly", fg)])
            style.configure("TCombobox",
                            fieldbackground=bg,
                            background=bg,
                            foreground=fg)
            site_selector.config(style="TCombobox")
        except Exception:
            pass


def _render_materials(materials: List[Dict[str, Any]]) -> None:
    if not material_frame:
        return

    _clear_material_display()

    bg = DARK_BG if dark_mode else LIGHT_BG
    fg = DARK_FG if dark_mode else LIGHT_FG
    green = DARK_GREEN if dark_mode else LIGHT_GREEN
    orange = DARK_ORANGE if dark_mode else LIGHT_ORANGE
    material_frame.config(bg=bg)

    headers = ["Material", "Required", "Provided", "Carrier", "Remaining"]
    for col, header_text in enumerate(headers):
        lbl = tk.Label(material_frame, text=header_text, font=("Helvetica", 8, "bold"),
                       anchor=tk.W, bg=bg, fg=fg)
        lbl.grid(row=0, column=col, sticky=tk.W, padx=(0, 8))

    sep = ttk.Separator(material_frame, orient=tk.HORIZONTAL)
    sep.grid(row=1, column=0, columnspan=len(headers), sticky=tk.EW, pady=2)

    for row_idx, mat in enumerate(materials, start=2):
        fg_color = green if mat["completion"] == 0 else orange

        name_lbl = tk.Label(material_frame, text=mat["name"], font=("Helvetica", 8),
                            fg=fg_color, bg=bg, anchor=tk.W)
        name_lbl.grid(row=row_idx, column=0, sticky=tk.W, padx=(0, 8))

        req_lbl = tk.Label(material_frame, text=str(mat["required"]), font=("Helvetica", 8),
                           fg=fg_color, bg=bg, anchor=tk.E)
        req_lbl.grid(row=row_idx, column=1, sticky=tk.E, padx=(0, 8))

        prov_lbl = tk.Label(material_frame, text=str(mat["provided"]), font=("Helvetica", 8),
                            fg=fg_color, bg=bg, anchor=tk.E)
        prov_lbl.grid(row=row_idx, column=2, sticky=tk.E, padx=(0, 8))

        carr_lbl = tk.Label(material_frame, text=str(mat["carrier"]), font=("Helvetica", 8),
                            fg=fg_color, bg=bg, anchor=tk.E)
        carr_lbl.grid(row=row_idx, column=3, sticky=tk.E, padx=(0, 8))

        comp_lbl = tk.Label(material_frame, text=str(mat["completion"]), font=("Helvetica", 8),
                            fg=fg_color, bg=bg, anchor=tk.E)
        comp_lbl.grid(row=row_idx, column=4, sticky=tk.E, padx=(0, 8))


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    global journal_dir

    if journal_dir is None:
        journal_dir = state.get("JournalDir")

    event_name = entry.get("event", "")

    if event_name == "Docked":
        _load_carrier_cargo()
        _update_carrier_amounts()
        _save_data()
        if selected_site_id:
            _update_display()

    elif event_name == "Cargo":
        _load_carrier_cargo()
        _update_carrier_amounts()
        _save_data()
        if selected_site_id:
            _update_display()

    elif event_name == "CargoTransfer":
        _load_carrier_cargo()
        _update_carrier_amounts()
        _save_data()
        if selected_site_id:
            _update_display()

    elif event_name == "ColonisationConstructionDepot":
        _load_carrier_cargo()
        _process_construction_depot(entry, station, system)

    elif event_name == "ColonisationContribution":
        _load_carrier_cargo()
        market_id = entry.get("MarketID")
        if market_id and market_id in construction_sites:
            contributions = entry.get("Contributions", [])
            for contrib in contributions:
                raw_name = contrib.get("Name", "")
                name_key = raw_name.replace("$", "").replace("_name;", "").lower()
                amount = contrib.get("Amount", 0)
                for mat in construction_sites[market_id]["materials"]:
                    if mat["name_key"] == name_key:
                        mat["provided"] += amount
                        mat["completion"] = _calculate_completion(
                            mat["required"], mat["provided"], mat["carrier"]
                        )
                        break
            _save_data()
            if market_id == selected_site_id:
                _update_display()
