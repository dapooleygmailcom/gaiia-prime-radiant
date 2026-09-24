"""
Comprehensive Combat Logs & Authentic Tank Status Displays (SSDs)
Renegade Legion Centurion: Liberator vs Horatius on Centurion Map 1
"""

import os
import sys
import json
import random

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from engine.simulation.dynamic_engine import DynamicEngine
from engine.kernel.spatial_models import HexCoordinateConverter


def render_ascii_armor_grid(grid_name: str, values: list, max_depth: int = None) -> str:
    """Renders a 2D ASCII diagram of an armor grid showing depth per column."""
    if not values:
        return f"  {grid_name}: [Empty]"
    
    if max_depth is None:
        max_depth = max(values) if values else 1
    if max_depth <= 0:
        max_depth = 1

    lines = [f"  +-- {grid_name.upper()} (Width: {len(values)}, Max Depth: {max_depth}) --+"]
    
    # Column indices
    col_hdr = "  | Col:  " + "".join(f"{i+1:2d} " for i in range(len(values))) + "|"
    lines.append(col_hdr)
    lines.append("  | Depth:" + "".join(f"{v:2d} " for v in values) + "|")
    
    # Visual grid bars
    for d in range(max_depth, 0, -1):
        bar = "  |       "
        for v in values:
            bar += "[#]" if v >= d else " . "
        bar += "|"
        lines.append(bar)
    lines.append("  +" + "-" * (len(col_hdr) - 4) + "+")
    return "\n".join(lines)


def render_ascii_internal_grid(int_name: str, matrix: list, comp_names: list) -> str:
    """Renders an ASCII diagram of an internal component bay matrix."""
    if not matrix:
        return f"  {int_name}: [Nominal / Not Tracked]"
    
    lines = [f"  +-- {int_name.upper()} MATRIX --+"]
    max_rows = max(len(col) for col in matrix) if matrix else 0
    
    for r_idx in range(max_rows):
        row_str = f"  | Row {r_idx+1:2d}: "
        for c_idx, col in enumerate(matrix):
            c_name = comp_names[c_idx][r_idx] if (c_idx < len(comp_names) and r_idx < len(comp_names[c_idx])) else "Empty"
            if c_name == "Empty":
                row_str += "  .   "
            elif r_idx < len(col) and col[r_idx]:
                row_str += "[DMG] "
            else:
                row_str += "[OK ] "
        row_str += "|"
        lines.append(row_str)
    
    lines.append("  +" + "-" * 50 + "+")
    # Legend of damaged components
    damaged = []
    for c_idx, col in enumerate(matrix):
        for r_idx, is_hit in enumerate(col):
            if is_hit:
                c_name = comp_names[c_idx][r_idx] if (c_idx < len(comp_names) and r_idx < len(comp_names[c_idx])) else f"Bay R{r_idx+1}"
                if c_name != "Empty":
                    damaged.append(f"Col {c_idx+1}, Row {r_idx+1}: {c_name}")
    if damaged:
        lines.append("  CRITICAL DAMAGE IN THIS BAY:")
        for d in damaged:
            lines.append(f"    * {d} [DESTROYED/OFFLINE]")
    else:
        lines.append("  All internal systems in this bay are 100% OPERATIONAL.")
    return "\n".join(lines)


def print_tank_ssd(unit, title: str = None):
    """
    Renders an authentic, detailed Centurion Tank Status Display (SSD).
    """
    profile = getattr(unit, 'entity_profile', {})
    attrs = profile.get("attributes", {})
    collections = profile.get("collections", {})
    grids = profile.get("grids", {})
    
    heading_labels = {1: "North (1)", 2: "North-East (2)", 3: "South-East (3)", 4: "South (4)", 5: "South-West (5)", 6: "North-West (6)"}
    heading_str = heading_labels.get(unit.heading, str(unit.heading))

    print("\n" + "=" * 85)
    print(f"  TANK STATUS DISPLAY (SSD) :: {unit.name.upper()} [{unit.id}]")
    if title:
        print(f"  Status: {title}")
    print("=" * 85)
    
    # 1. Identification & Vassal Counter Binding
    print("\n[IDENTIFICATION & VASSAL COUNTER BINDING]")
    print(f"  Faction:           {unit.faction.upper()}")
    print(f"  Counter Name:      {getattr(unit, 'counter_name', unit.name)}")
    print(f"  Counter Image:     {getattr(unit, 'counter_image', 'N/A')}")
    print(f"  Vassal Prototype:  {getattr(unit, 'counter_prototype', 'N/A')}")
    print(f"  Map Coordinate:    Hex {unit.position} (Centurion Map 1)")
    print(f"  Heading (Facing):  {heading_str}")
    print(f"  Current Velocity:  {unit.velocity} hexes/turn")
    print(f"  Thrust Capacity:   {unit.thrust_points} / {attrs.get('Maximum Thrust', unit.thrust_points)} MP")

    # 2. Weapons & Ammunition
    print("\n[TACTICAL WEAPON ARRAYS & AMMUNITION]")
    weapons = collections.get("Weapons", [])
    print(f"  {'Weapon Name':<28} | {'Location':<10} | {'Range':<8} | {'Ammo Count':<14} | {'Damage Template'}")
    print("  " + "-" * 80)
    for w in weapons:
        w_name = w.get("Name", "Unknown")
        loc = w.get("Location", "Hull")
        rng = str(w.get("Range", "N/A"))
        
        # Ammo classification
        if "TVLG" in w_name:
            ammo_str = f"{getattr(unit, 'tvlg_ammo', 4)} rounds"
            tmpl_str = "TVLG Inverted-T [2, 2, 5, 2, 2]"
        elif "SMLM" in w_name:
            ammo_str = f"{getattr(unit, 'smlm_ammo', 2)} rounds"
            tmpl_str = "SMLM Template [1, 2, 2, 1]"
        elif "150mm" in w_name:
            ammo_str = "Unlimited"
            tmpl_str = "Gauss Template [2, 4, 2]"
        elif "50mm" in w_name:
            ammo_str = "Unlimited"
            tmpl_str = "Gauss Template [1, 2, 1]"
        elif "5/6" in w_name or "Laser" in w_name:
            ammo_str = "Unlimited"
            tmpl_str = "Laser Column [5]"
        elif "Vulcan" in w_name:
            ammo_str = "Unlimited"
            tmpl_str = "Point Defense [1, 1, 1, 1, 1]"
        else:
            ammo_str = "Unlimited"
            tmpl_str = str(w.get("Damage", "Standard"))
            
        print(f"  {w_name:<28} | {loc:<10} | {rng:<8} | {ammo_str:<14} | {tmpl_str}")

    # 3. Defensive Shields & Target SF
    print("\n[DEFENSIVE SHIELD FACTORS & ECM]")
    sf_info = []
    for g_name, g_data in grids.items():
        if "SF" in g_data:
            sf_info.append(f"{g_name.replace(' Armor','')}: SF {g_data['SF']}")
    print(f"  Directional Shields: {', '.join(sf_info)}")
    print(f"  Target Painting:     Painting Laser Equipped (Max 20 Hexes)")

    # 4. Authoritative Armor Grids
    print("\n[AUTHORITATIVE ARMOR INTEGRITY GRIDS]")
    if hasattr(unit, 'damage_state') and unit.damage_state.armor_grids:
        for grid_name, values in unit.damage_state.armor_grids.items():
            orig_depth = grids.get(grid_name, {}).get("Depth", max(values) if values else 1)
            print(render_ascii_armor_grid(grid_name, values, max_depth=orig_depth))
            print()

    # 5. Internal Component Grids
    print("[INTERNAL COMPONENT BAYS & CRITICAL HIT MATRICES]")
    if hasattr(unit, 'damage_state') and unit.damage_state.internal_grids:
        for int_name, grid_matrix in unit.damage_state.internal_grids.items():
            comp_names = grids.get(int_name, {}).get("Columns", [])
            print(render_ascii_internal_grid(int_name, grid_matrix, comp_names))
            print()
    print("=" * 85 + "\n")


def execute_combat_simulation():
    # 1. Initialize Engine
    engine = DynamicEngine("centurion_combat_ssd_demo")
    engine.add_commander("commonwealth")
    engine.add_commander("tog")

    # 2. Ingest Centurion Map 1 from Vassal Module
    vmod_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "data/vassal_modules/Renegade_Legion_Centurion_1.2.vmod"
    ))
    engine.load_vassal_map(vmod_path, board_id="map_1")

    # 3. Create Units from RAG-Doll / Entity definitions
    lib = engine.wsm.create_unit_from_entity("lib1", "commonwealth", "rl_liberator_medium_grav_tank", engine.rules)
    lib.position = "0605"
    lib.heading = 3  # Facing South-East (towards 0610)
    lib.velocity = 0
    lib.thrust_points = 6
    lib.tvlg_ammo = 4

    hor = engine.wsm.create_unit_from_entity("hor1", "tog", "tog_horatius_medium_grav_tank", engine.rules)
    hor.position = "0610"
    hor.heading = 6  # Facing North-West (towards 0605)
    hor.velocity = 0
    hor.thrust_points = 6
    hor.smlm_ammo = 2

    # Print Initial SSDs
    print("=" * 85)
    print("     GAIIA PRIME RADIANT — CENTURION SIMULATION (LIBERATOR vs HORATIUS)")
    print("     Map: Centurion Vassal Map 1 (660 Hexes) | Range: 5 Hexes")
    print("=" * 85)
    
    print("\n" + "=" * 85)
    print("                     PRE-COMBAT AUTHORITATIVE TANK STATUS DISPLAYS")
    print("=" * 85)
    print_tank_ssd(lib, title="PRE-COMBAT (Commonwealth Liberator)")
    print_tank_ssd(hor, title="PRE-COMBAT (TOG Horatius)")

    # Execute Combat Phase
    from seed_mechanics import resolve_combat_code
    exec(resolve_combat_code, engine.dynamic_globals, engine.dynamic_globals)
    resolve_combat = engine.dynamic_globals.get("resolve_combat")

    print("=" * 85)
    print("                         AUTHORITATIVE COMBAT LOGS")
    print("=" * 85)
    
    # Check LOS & Range
    is_clear, blockers, reason = engine.check_los("lib1", "hor1")
    c1 = HexCoordinateConverter.parse_coord(lib.position)
    c2 = HexCoordinateConverter.parse_coord(hor.position)
    dist = HexCoordinateConverter.cube_distance(
        HexCoordinateConverter.axial_to_cube(*HexCoordinateConverter.col_row_to_axial(c1[0], c1[1])),
        HexCoordinateConverter.axial_to_cube(*HexCoordinateConverter.col_row_to_axial(c2[0], c2[1]))
    )
    
    print(f"\n[ENGAGEMENT GEOMETRY]")
    print(f"  Attacker:       Liberator [lib1] at Hex 0605 (Heading: 3 / SE)")
    print(f"  Target:         Horatius  [hor1] at Hex 0610 (Heading: 6 / NW)")
    print(f"  Distance:       {dist} Tactical Hexes (Medium Range Band 4-6 | Base To-Hit: 10)")
    print(f"  Line of Sight:  {'CLEAR' if is_clear else 'BLOCKED'} ({reason})")
    print(f"  Target Facings: Liberator -> Horatius: Front Facing (SF: {hor.entity_profile.get('grids',{}).get('Front Armor',{}).get('SF',6)})")
    print(f"                  Horatius  -> Liberator: Front Facing (SF: {lib.entity_profile.get('grids',{}).get('Front Armor',{}).get('SF',6)})")

    # VOLLEY 1: Liberator Alpha Strike
    print("\n" + "-" * 85)
    print(" [VOLLEY 1] COMMONWEALTH LIBERATOR ALPHA STRIKE ON TOG HORATIUS")
    print(" Weapons Declared: Painting Laser, 150mm Turret Gauss Cannon, 5/6 Laser, TVLG(4) Missile Battery")
    print(" Command String:   [FIRE: Target=hor1, Weapons=150mm;5/6 Laser;TVLG(4), Painting=True]")
    print("-" * 85)
    
    # We pass seed for reproducibility
    res_cw = resolve_combat(
        lib, hor, engine.wsm,
        "[FIRE: Target=hor1, Weapons=150mm;5/6 Laser;TVLG(4), Painting=True]",
        seed=105
    )
    
    print(f"\n  Target Facing:        {res_cw.get('facing')} (Target SF: {res_cw.get('target_sf')})")
    print(f"  Painting Laser Roll:  Roll {res_cw.get('painting_roll')} vs Target Number (Base 10 - Target SF {res_cw.get('target_sf')} = 4)")
    print(f"  Painting Laser Lock:  {'SUCCESSFUL! (Target Shields Negated for this turn)' if res_cw.get('painting_hit') else 'FAILED (Target SF applies to energy & missile weapons)'}")
    print(f"  Eligible Weapons:     {', '.join(res_cw.get('eligible_weapons', []))}")
    
    print("\n  Individual Weapon Firing & Damage Resolutions:")
    for shot in res_cw.get("shots", []):
        w_name = shot.get("weapon")
        roll = shot.get("roll")
        to_hit = shot.get("modified_to_hit")
        hit = shot.get("hit")
        sh_mod = shot.get("modifiers", {}).get("shield", 0)
        print(f"\n    * Weapon: {w_name}")
        print(f"      To-Hit Calculation: Base {shot.get('base_to_hit')} + ShieldMod {sh_mod} = Modified {to_hit}")
        print(f"      1d10 Roll:          {roll} -> [{'HIT' if hit else 'MISS'}]")
        
        if hit and shot.get("damage"):
            dmg = shot["damage"]
            print(f"      Target Grid:        {dmg.get('grid')} (Impact Center: Col {dmg.get('impact_column')})")
            print(f"      Damage Template:    {dmg.get('template')} -> Total Armor Absorbed: {dmg.get('total_armor_damage')} pts")
            print(f"      Column-by-Column Impact:")
            for cr in dmg.get("column_records", []):
                excess_str = f" | EXCESSS PENETRATION: {cr['excess_penetration']} pts into Internals!" if cr['excess_penetration'] > 0 else ""
                print(f"        - Column {cr['column']:2d}: Inbound Pen={cr['penetration']}, Armor Absorbed={cr['armor_absorbed']}, Remaining Armor Depth={cr['remaining_armor']}{excess_str}")
            if dmg.get("internal_hits"):
                print(f"      CRITICAL INTERNAL DAMAGE:")
                for ih in dmg.get("internal_hits"):
                    print(f"        ! INTERNAL HIT: {ih}")

    # VOLLEY 2: Horatius Return Fire
    print("\n" + "-" * 85)
    print(" [VOLLEY 2] TOG HORATIUS RETURN FIRE ON COMMONWEALTH LIBERATOR")
    print(" Weapons Declared: Painting Laser, 150mm Gauss Cannon, 5/6 Laser, SMLM(2) Missile Battery")
    print(" Command String:   [FIRE: Target=lib1, Weapons=150mm;5/6 Laser;SMLM (2), Painting=True]")
    print("-" * 85)
    
    res_tog = resolve_combat(
        hor, lib, engine.wsm,
        "[FIRE: Target=lib1, Weapons=150mm;5/6 Laser;SMLM (2), Painting=True]",
        seed=204
    )
    
    print(f"\n  Target Facing:        {res_tog.get('facing')} (Target SF: {res_tog.get('target_sf')})")
    print(f"  Painting Laser Roll:  Roll {res_tog.get('painting_roll')} vs Target Number (Base 10 - Target SF {res_tog.get('target_sf')} = 4)")
    print(f"  Painting Laser Lock:  {'SUCCESSFUL! (Target Shields Negated for this turn)' if res_tog.get('painting_hit') else 'FAILED (Target SF applies to energy & missile weapons)'}")
    print(f"  Eligible Weapons:     {', '.join(res_tog.get('eligible_weapons', []))}")
    
    print("\n  Individual Weapon Firing & Damage Resolutions:")
    for shot in res_tog.get("shots", []):
        w_name = shot.get("weapon")
        roll = shot.get("roll")
        to_hit = shot.get("modified_to_hit")
        hit = shot.get("hit")
        sh_mod = shot.get("modifiers", {}).get("shield", 0)
        print(f"\n    * Weapon: {w_name}")
        print(f"      To-Hit Calculation: Base {shot.get('base_to_hit')} + ShieldMod {sh_mod} = Modified {to_hit}")
        print(f"      1d10 Roll:          {roll} -> [{'HIT' if hit else 'MISS'}]")
        
        if hit and shot.get("damage"):
            dmg = shot["damage"]
            print(f"      Target Grid:        {dmg.get('grid')} (Impact Center: Col {dmg.get('impact_column')})")
            print(f"      Damage Template:    {dmg.get('template')} -> Total Armor Absorbed: {dmg.get('total_armor_damage')} pts")
            print(f"      Column-by-Column Impact:")
            for cr in dmg.get("column_records", []):
                excess_str = f" | EXCESSS PENETRATION: {cr['excess_penetration']} pts into Internals!" if cr['excess_penetration'] > 0 else ""
                print(f"        - Column {cr['column']:2d}: Inbound Pen={cr['penetration']}, Armor Absorbed={cr['armor_absorbed']}, Remaining Armor Depth={cr['remaining_armor']}{excess_str}")
            if dmg.get("internal_hits"):
                print(f"      CRITICAL INTERNAL DAMAGE:")
                for ih in dmg.get("internal_hits"):
                    print(f"        ! INTERNAL HIT: {ih}")

    # Print Post-Combat SSDs
    print("\n" + "=" * 85)
    print("                     POST-COMBAT AUTHORITATIVE TANK STATUS DISPLAYS")
    print("=" * 85)
    print_tank_ssd(lib, title="POST-COMBAT (Commonwealth Liberator — Post Return Fire)")
    print_tank_ssd(hor, title="POST-COMBAT (TOG Horatius — Post Alpha Strike)")


if __name__ == "__main__":
    execute_combat_simulation()
