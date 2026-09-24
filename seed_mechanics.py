import sqlite3

db_path = "state/cache/rule_cache.db"

def inject_mechanic(mechanic_name, python_code):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compiled_mechanics (
                mechanic_name TEXT PRIMARY KEY,
                python_code TEXT,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            INSERT OR REPLACE INTO compiled_mechanics (mechanic_name, python_code, last_accessed)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (mechanic_name, python_code))

# ─────────────────────────────────────────────────────────────
# calculate_movement_options (Pathfinding Graph Generator)
# ─────────────────────────────────────────────────────────────
calculate_movement_options_code = r"""
from collections import deque

VALID_HEX_DIRS = {
    "N": (0, -1),
    "NE": (1, 0),
    "SE": (1, 1),
    "S": (0, 1),
    "SW": (-1, 0),
    "NW": (-1, -1)
}

DIR_TO_HEADING = {
    (0, -1): 1,
    (1, 0): 2,
    (1, 1): 3,
    (0, 1): 4,
    (-1, 0): 5,
    (-1, -1): 6
}

TERRAIN_MOVEMENT_COST = {
    "Clear": 1,
    "River": 1,
    "Light Woods": 2,
    "Heavy Woods": 3,
    "Rough": 2,
    "Water": 2
}

def calculate_movement_options(unit, wsm):
    options = {} # (end_hex, end_vel, end_heading) -> {thrust_cost, path}
    
    start_pos = unit.position
    start_vel = unit.velocity
    max_thrust = unit.thrust_points
    
    def turn_radius(velocity):
        return int(velocity / 5)
        
    def terrain_cost(hex_coord, prev_hex):
        hex_data = wsm.get_state().map_hexes.get(hex_coord, {})
        terrain = hex_data.get("terrain", "Clear")
        base = TERRAIN_MOVEMENT_COST.get(terrain, 1)
        if prev_hex:
            prev_data = wsm.get_state().map_hexes.get(prev_hex, {})
            elev_gain = hex_data.get("elevation", 0) - prev_data.get("elevation", 0)
            if elev_gain > 0:
                base += elev_gain
        return base
        
    max_possible_vel = start_vel + max_thrust
    min_possible_vel = max(0, start_vel - max_thrust)
    
    for end_vel in range(min_possible_vel, max_possible_vel + 1):
        vel_thrust = abs(end_vel - start_vel)
        if vel_thrust > max_thrust:
            continue
            
        movement_budget = max(start_vel, end_vel)
        
        queue = deque()
        queue.append((start_pos, unit.heading, 0, 0, []))
        
        valid_paths = []
        
        while queue:
            curr_hex, curr_heading, h_since_turn, t_cost, path = queue.popleft()
            
            if t_cost == movement_budget:
                valid_paths.append((curr_hex, curr_heading, path))
                continue
            elif t_cost > movement_budget:
                continue
                
            try:
                x, y = int(curr_hex[:2]), int(curr_hex[2:])
            except ValueError:
                continue
            
            for dname, (dx, dy) in VALID_HEX_DIRS.items():
                nx, ny = x + dx, y + dy
                next_hex = f"{nx:02d}{ny:02d}"
                next_step_heading = DIR_TO_HEADING[(dx, dy)]
                
                next_h_since_turn = h_since_turn
                if next_step_heading != curr_heading:
                    facing_change = min((next_step_heading - curr_heading) % 6, (curr_heading - next_step_heading) % 6)
                    required = turn_radius(end_vel) * facing_change
                    if h_since_turn < required:
                        continue 
                    next_h_since_turn = 0
                
                next_h_since_turn += 1
                next_t_cost = t_cost + terrain_cost(next_hex, curr_hex)
                
                if next_t_cost <= movement_budget:
                    queue.append((next_hex, next_step_heading, next_h_since_turn, next_t_cost, path + [next_hex]))
                    
        thrust_left_for_heading = max_thrust - vel_thrust
        
        for p_hex, p_heading, p_path in valid_paths:
            for dh in range(-thrust_left_for_heading, thrust_left_for_heading + 1):
                final_heading = ((p_heading - 1 + dh) % 6) + 1
                heading_thrust = abs(dh)
                total_thrust = vel_thrust + heading_thrust
                
                if total_thrust <= max_thrust:
                    key = (p_hex, end_vel, final_heading)
                    if key not in options or options[key]['thrust_cost'] > total_thrust:
                        options[key] = {
                            'end_vel': end_vel,
                            'end_heading': final_heading,
                            'thrust_cost': total_thrust,
                            'path': p_path
                        }
                        
    hex_map = {}
    for (h, vel, head), data in options.items():
        if h not in hex_map:
            hex_map[h] = []
        hex_map[h].append({
            'vel': vel,
            'heading': head,
            'thrust': data['thrust_cost'],
            'path': data['path']
        })
        
    return hex_map
"""

# ─────────────────────────────────────────────────────────────
# resolve_movement  (Simplified to use Reachability Graph)
# ─────────────────────────────────────────────────────────────
resolve_movement_code = r"""
import re

def resolve_movement(unit, wsm, command_string):
    # Parse LLM simplified command format
    # [MOVE: TargetHex=1210, EndVelocity=3, EndHeading=4]
    
    target_match = re.search(r'TargetHex=(\d{4})', command_string, re.IGNORECASE)
    if not target_match:
        # Fallback to Path= if they used the old syntax by accident
        target_match = re.search(r'Path=[0-9,]*?(\d{4})(?:\]|\s|$)', command_string, re.IGNORECASE)
        if not target_match:
            raise ValueError(f"Could not parse TargetHex from command: {command_string}. Please use [MOVE: TargetHex=..., EndVelocity=..., EndHeading=...]")
    target_hex = target_match.group(1)

    vel_match = re.search(r'EndVelocity=(\d+)', command_string, re.IGNORECASE)
    end_vel = int(vel_match.group(1)) if vel_match else unit.velocity

    heading_match = re.search(r'EndHeading=(\d+)', command_string, re.IGNORECASE)
    if not heading_match:
        heading_match = re.search(r'Heading=(\d+)', command_string, re.IGNORECASE)
    new_heading = int(heading_match.group(1)) if heading_match else unit.heading

    if target_hex == unit.position and end_vel == unit.velocity and new_heading == unit.heading:
        return # No movement

    # Query pathfinding options to see if this is valid
    from collections import deque
    
    def get_reachability(u, w):
        options = {}
        start_pos = u.position
        start_vel = u.velocity
        max_thrust = u.thrust_points
        
        def turn_radius(velocity):
            return int(velocity / 5)
            
        def terrain_cost(hex_coord, prev_hex):
            hex_data = w.get_state().map_hexes.get(hex_coord, {})
            terrain = hex_data.get("terrain", "Clear")
            base = {"Clear": 1, "River": 1, "Light Woods": 2, "Heavy Woods": 3, "Rough": 2, "Water": 2}.get(terrain, 1)
            if prev_hex:
                prev_data = w.get_state().map_hexes.get(prev_hex, {})
                elev_gain = hex_data.get("elevation", 0) - prev_data.get("elevation", 0)
                if elev_gain > 0:
                    base += elev_gain
            return base
            
        max_possible_vel = start_vel + max_thrust
        min_possible_vel = max(0, start_vel - max_thrust)
        
        for e_vel in range(min_possible_vel, max_possible_vel + 1):
            vel_thrust = abs(e_vel - start_vel)
            if vel_thrust > max_thrust:
                continue
                
            movement_budget = max(start_vel, e_vel)
            
            queue = deque()
            queue.append((start_pos, u.heading, 0, 0, []))
            valid_paths = []
            
            while queue:
                curr_hex, curr_heading, h_since_turn, t_cost, path = queue.popleft()
                
                if t_cost == movement_budget:
                    valid_paths.append((curr_hex, curr_heading, path))
                    continue
                elif t_cost > movement_budget:
                    continue
                    
                try:
                    x, y = int(curr_hex[:2]), int(curr_hex[2:])
                except ValueError:
                    continue
                
                dirs = {"N":(0,-1), "NE":(1,0), "SE":(1,1), "S":(0,1), "SW":(-1,0), "NW":(-1,-1)}
                dir_to_head = {(0,-1):1, (1,0):2, (1,1):3, (0,1):4, (-1,0):5, (-1,-1):6}
                
                for dname, (dx, dy) in dirs.items():
                    nx, ny = x + dx, y + dy
                    next_hex = f"{nx:02d}{ny:02d}"
                    next_step_heading = dir_to_head[(dx, dy)]
                    
                    next_h_since_turn = h_since_turn
                    if next_step_heading != curr_heading:
                        facing_change = min((next_step_heading - curr_heading) % 6, (curr_heading - next_step_heading) % 6)
                        required = turn_radius(e_vel) * facing_change
                        if h_since_turn < required:
                            continue 
                        next_h_since_turn = 0
                    
                    next_h_since_turn += 1
                    next_t_cost = t_cost + terrain_cost(next_hex, curr_hex)
                    
                    if next_t_cost <= movement_budget:
                        queue.append((next_hex, next_step_heading, next_h_since_turn, next_t_cost, path + [next_hex]))
                        
            thrust_left_for_heading = max_thrust - vel_thrust
            for p_hex, p_heading, p_path in valid_paths:
                for dh in range(-thrust_left_for_heading, thrust_left_for_heading + 1):
                    final_heading = ((p_heading - 1 + dh) % 6) + 1
                    heading_thrust = abs(dh)
                    total_thrust = vel_thrust + heading_thrust
                    
                    if total_thrust <= max_thrust:
                        key = (p_hex, e_vel, final_heading)
                        if key not in options or options[key]['thrust_cost'] > total_thrust:
                            options[key] = {
                                'end_vel': e_vel,
                                'end_heading': final_heading,
                                'thrust_cost': total_thrust,
                                'path': p_path
                            }
                            
        hex_map = {}
        for (h, vel, head), data in options.items():
            if h not in hex_map:
                hex_map[h] = []
            hex_map[h].append({
                'vel': vel,
                'heading': head,
                'thrust': data['thrust_cost'],
                'path': data['path']
            })
        return hex_map

    options_map = get_reachability(unit, wsm)
    
    if target_hex not in options_map:
        raise ValueError(f"Hex {target_hex} is unreachable from your position with current velocity/thrust constraints.")
        
    valid_options = options_map[target_hex]
    
    # Find matching option
    matching = [o for o in valid_options if o['vel'] == end_vel and o['heading'] == new_heading]
    
    if not matching:
        available = ", ".join([f"(vel:{o['vel']}, head:{o['heading']})" for o in valid_options])
        raise ValueError(f"TargetHex {target_hex} is reachable, but not with EndVelocity={end_vel} and EndHeading={new_heading}. Valid combos are: {available}")
        
    best_option = min(matching, key=lambda o: o['thrust'])
    
    # Apply
    if best_option['path']:
        unit.position = best_option['path'][-1]
    unit.velocity = best_option['vel']
    unit.heading = best_option['heading']
    unit.thrust_points -= best_option['thrust']
"""

# ─────────────────────────────────────────────────────────────
# get_movement_stats
# ─────────────────────────────────────────────────────────────
get_movement_stats_code = """
def get_movement_stats(unit, wsm):
    profile = getattr(unit, 'entity_profile', {})
    attrs = profile.get('attributes', {})
    max_thrust = attrs.get('Maximum Thrust', 0)
    safe_speed = max_thrust
    max_velocity = max_thrust * 2
    return {
        'max_velocity': max_velocity,
        'max_thrust': max_thrust,
        'safe_speed': safe_speed
    }
"""

# ─────────────────────────────────────────────────────────────
# calculate_turn_radius  (Fix TC4 seeding)
# ─────────────────────────────────────────────────────────────
calculate_turn_radius_code = """
def calculate_turn_radius(velocity):
    # Renegade Legion: velocity 1-4=0, 5-9=1, 10-14=2, 15-19=3 hexes before facing change
    return int(velocity / 5)
"""

inject_mechanic("calculate_movement_options", calculate_movement_options_code)
inject_mechanic("resolve_movement", resolve_movement_code)
inject_mechanic("get_movement_stats", get_movement_stats_code)
inject_mechanic("calculate_turn_radius", calculate_turn_radius_code)

print("Mechanics seeded successfully!")
print("  resolve_movement : adjacency(6-dir), turn-radius, terrain-cost, thrust-validate-before-mutate")
print("  get_movement_stats : max_thrust, safe_speed, max_velocity")
print("  calculate_turn_radius : velocity -> hexes before facing change")


# ─────────────────────────────────────────────────────────────
# calculate_hex_range  (rhombus offset-hex grid distance)
# ─────────────────────────────────────────────────────────────
calculate_hex_range_code = """
def calculate_hex_range(pos_a, pos_b):
    x1, y1 = int(pos_a[:2]), int(pos_a[2:])
    x2, y2 = int(pos_b[:2]), int(pos_b[2:])
    dx, dy = x2 - x1, y2 - y1
    if (dx >= 0 and dy >= 0) or (dx <= 0 and dy <= 0):
        return max(abs(dx), abs(dy))
    return abs(dx) + abs(dy)
"""

# ─────────────────────────────────────────────────────────────
# check_los  (Smoke blocks LOS per SMOKE rule)
# ─────────────────────────────────────────────────────────────
check_los_code = """
def check_los(attacker_pos, target_pos, wsm):
    x1, y1 = int(attacker_pos[:2]), int(attacker_pos[2:])
    x2, y2 = int(target_pos[:2]), int(target_pos[2:])
    dx, dy = x2 - x1, y2 - y1
    n = (max(abs(dx), abs(dy)) if ((dx >= 0 and dy >= 0) or (dx <= 0 and dy <= 0))
         else abs(dx) + abs(dy))
    if n == 0:
        return True, ""
    for i in range(1, n):
        t = i / n
        hid = f"{round(x1 + t*(x2-x1)):02d}{round(y1 + t*(y2-y1)):02d}"
        if wsm.get_state().map_hexes.get(hid, {}).get("terrain") == "Smoke":
            return False, f"Smoke hex {hid} blocks LOS"
    return True, ""
"""

# ─────────────────────────────────────────────────────────────
# resolve_combat  (all rules sourced from RAG-Doll & Centurion SSDs)
# ─────────────────────────────────────────────────────────────
resolve_combat_code = r"""
import re
import random

def _base_to_hit(r):
    if r <= 1:   return 12
    if r <= 3:   return 11
    if r <= 6:   return 10
    if r <= 10:  return 9
    if r <= 15:  return 8
    if r <= 20:  return 7
    return 6

TERRAIN_TO_HIT_MOD = {
    "Light Woods": -1,
    "Heavy Woods": -2,
    "Smoke":       -2,
}

HEADING_TO_DIR = {1:(0,-1),2:(1,0),3:(1,1),4:(0,1),5:(-1,0),6:(-1,-1)}

DAMAGE_TEMPLATES = {
    "150mm":     {"pattern": [2, 4, 2], "center": 1, "name": "150mm Gauss Template [2, 4, 2]"},
    "50mm":      {"pattern": [1, 2, 1], "center": 1, "name": "50mm Gauss Template [1, 2, 1]"},
    "5/6 Laser": {"pattern": [5],       "center": 0, "name": "5/6 Laser Column [5]"},
    "3/6 Laser": {"pattern": [4],       "center": 0, "name": "3/6 Laser Column [4]"},
    "Laser":     {"pattern": [5],       "center": 0, "name": "Laser Column [5]"},
    "TVLG":      {"pattern": [2, 2, 5, 2, 2], "center": 2, "name": "TVLG Inverted-T Template [2, 2, 5, 2, 2]"},
    "SMLM":      {"pattern": [1, 2, 2, 1], "center": 1, "name": "SMLM Missile Template [1, 2, 2, 1]"},
    "Vulcan":    {"pattern": [1, 1, 1, 1, 1], "center": 2, "name": "Vulcan PD Spread [1, 1, 1, 1, 1]"}
}

def _get_weapon_template(wname):
    w_low = wname.lower()
    if "150mm" in w_low: return DAMAGE_TEMPLATES["150mm"]
    if "50mm" in w_low:  return DAMAGE_TEMPLATES["50mm"]
    if "5/6" in w_low or ("laser" in w_low and "5" in w_low): return DAMAGE_TEMPLATES["5/6 Laser"]
    if "3/6" in w_low or ("laser" in w_low and "3" in w_low): return DAMAGE_TEMPLATES["3/6 Laser"]
    if "tvlg" in w_low:  return DAMAGE_TEMPLATES["TVLG"]
    if "smlm" in w_low:  return DAMAGE_TEMPLATES["SMLM"]
    if "vulcan" in w_low: return DAMAGE_TEMPLATES["Vulcan"]
    if "laser" in w_low: return DAMAGE_TEMPLATES["Laser"]
    return {"pattern": [3], "center": 0, "name": f"{wname} Standard"}

def _hex_range(a, b):
    x1,y1=int(a[:2]),int(a[2:]); x2,y2=int(b[:2]),int(b[2:])
    dx,dy=x2-x1,y2-y1
    return (max(abs(dx),abs(dy)) if ((dx>=0 and dy>=0) or (dx<=0 and dy<=0)) else abs(dx)+abs(dy))

def _check_los(ap, tp, wsm):
    x1,y1=int(ap[:2]),int(ap[2:]); x2,y2=int(tp[:2]),int(tp[2:])
    dx,dy=x2-x1,y2-y1
    n=(max(abs(dx),abs(dy)) if ((dx>=0 and dy>=0) or (dx<=0 and dy<=0)) else abs(dx)+abs(dy))
    for i in range(1,n):
        t=i/n
        hid=f"{round(x1+t*(x2-x1)):02d}{round(y1+t*(y2-y1)):02d}"
        if wsm.get_state().map_hexes.get(hid,{}).get("terrain")=="Smoke":
            return False, f"Smoke hex {hid} blocks LOS"
    return True,""

def _determine_facing(ap, tp, target_heading):
    x1,y1=int(tp[:2]),int(tp[2:]); x2,y2=int(ap[:2]),int(ap[2:])
    dx,dy=x2-x1,y2-y1
    if dx==0 and dy==0: return "Front"
    best_h,best_score=1,-9999
    for h,(ddx,ddy) in HEADING_TO_DIR.items():
        s=dx*ddx+dy*ddy
        if s>best_score: best_score,best_h=s,h
    diff=(best_h-target_heading)%6
    return {0:"Front",1:"Right",2:"Right",3:"Stern",4:"Left",5:"Left"}[diff]

def _shields_apply(wname):
    # Gauss weapons ignore shields; Lasers, Missiles are affected
    return not any(k in wname.lower() for k in ["gauss", "150mm", "50mm", "cannon", "mortar"])

def _get_sf(target, facing):
    grids=getattr(target,'entity_profile',{}).get('grids',{})
    gmap={"Front":"Front Armor","Stern":"Stern Armor","Left":"Left Armor","Right":"Right Armor","Turret":"Turret Armor"}
    return grids.get(gmap.get(facing,"Front Armor"),{}).get("SF",0)

def _apply_damage(target, facing, weapon_name, center_col=None):
    gmap = {
        "Front":  ("Front Armor",  "Front Internals"),
        "Stern":  ("Stern Armor",  "Stern Internals"),
        "Left":   ("Left Armor",   "Left Internals"),
        "Right":  ("Right Armor",  "Right Internals"),
        "Turret": ("Turret Armor", "Turret Internals")
    }
    armor_key, int_key = gmap.get(facing, ("Front Armor", "Front Internals"))
    armor_cols = getattr(target, 'damage_state', None) and target.damage_state.armor_grids.get(armor_key)
    
    if armor_cols is None and hasattr(target, 'damage_state'):
        # Fallback search
        for k in target.damage_state.armor_grids:
            if facing.lower() in k.lower():
                armor_key = k
                armor_cols = target.damage_state.armor_grids[k]
                break
                
    if armor_cols is None:
        armor_cols = [0] * 10
        
    num_cols = len(armor_cols)
    if center_col is None:
        center_col = random.randint(0, num_cols - 1)
        
    tmpl = _get_weapon_template(weapon_name)
    pattern = tmpl["pattern"]
    center_idx = tmpl["center"]
    
    col_records = []
    internal_hits = []
    total_armor_damage = 0
    
    int_cols_profile = getattr(target, 'entity_profile', {}).get('grids', {}).get(int_key, {}).get('Columns', [])
    int_matrix = getattr(target, 'damage_state', None) and target.damage_state.internal_grids.get(int_key)
    
    for offset, penetration in enumerate(pattern):
        c_idx = center_col + (offset - center_idx)
        if 0 <= c_idx < num_cols:
            orig_depth = armor_cols[c_idx]
            dmg_to_armor = min(orig_depth, penetration)
            armor_cols[c_idx] = max(0, orig_depth - penetration)
            total_armor_damage += dmg_to_armor
            excess = penetration - orig_depth
            
            penetrated_comps = []
            if excess > 0:
                if int_matrix and c_idx < len(int_matrix):
                    col_bays = int_matrix[c_idx]
                    comp_names = int_cols_profile[c_idx] if c_idx < len(int_cols_profile) else []
                    
                    for r_idx in range(min(excess, len(col_bays))):
                        col_bays[r_idx] = True
                        c_name = comp_names[r_idx] if r_idx < len(comp_names) else f"Bay R{r_idx+1}"
                        if c_name and c_name != "Empty":
                            penetrated_comps.append(c_name)
                            internal_hits.append(f"Col {c_idx+1} ({c_name})")
                            
            col_records.append({
                "column": c_idx + 1,
                "penetration": penetration,
                "armor_absorbed": dmg_to_armor,
                "remaining_armor": armor_cols[c_idx],
                "excess_penetration": max(0, excess),
                "internal_hits": penetrated_comps
            })
            
    return {
        "grid": armor_key,
        "column": center_col,
        "impact_column": center_col + 1,
        "template": tmpl["name"],
        "pattern": pattern,
        "damage": total_armor_damage,
        "armor_damage": total_armor_damage,
        "remaining": armor_cols[center_col] if 0 <= center_col < len(armor_cols) else 0,
        "column_records": col_records,
        "internal_hits": internal_hits
    }

def resolve_combat(attacker, target, wsm, command_string, seed=None):
    '''
    Resolve [FIRE: Target=<id>, Weapons=<w1;w2;...>, Painting=True/False].

    Rules (RAG-sourced & Authentic Centurion Mechanics):
    - Range->to-hit: 1=12, 2-3=11, 4-6=10, 7-10=9, 11-15=8, 16-20=7, off=6
    - Roll 1d10; hit if <= to-hit (1=auto-hit, 10=auto-miss)
    - Terrain mod (target hex): LightWoods -1, HeavyWoods/Smoke -2
    - Shield Factor (SF): Reduces to-hit for Painting Laser, Energy Lasers, Missiles; Gauss NOT affected
    - Painting laser: Roll vs (base - terrain - hull_down - target_facing_sf); if hit -> negates target SF for all friendly attacks this turn
    - Hull down: -2 to-hit; all hits resolve against Turret armor
    - Smoke in LOS -> ValueError (cannot fire)
    - Gauss & Lasers & Vulcans: Unlimited ammunition
    - Missiles (TVLG, SMLM): Limited ammunition as tracked on SSD (e.g. TVLG=4, SMLM=2)
    - Damage: Full 2D template resolution across columns + internal penetration
    '''
    if seed is not None:
        random.seed(seed)

    wm=re.search(r'Weapons=([^,\]]+(?:;[^,\]]+)*)',command_string,re.IGNORECASE)
    weapon_names=[w.strip() for w in wm.group(1).split(';')] if wm else []
    painting=bool(re.search(r'Painting\s*=\s*True',command_string,re.IGNORECASE))
    hull_down=getattr(target,'hull_down',False)

    range_hexes=_hex_range(attacker.position,target.position)
    los_clear,los_reason=_check_los(attacker.position,target.position,wsm)
    if not los_clear:
        raise ValueError(f"Cannot fire: {los_reason}")

    facing="Turret" if hull_down else _determine_facing(attacker.position,target.position,target.heading)
    target_terrain=wsm.get_state().map_hexes.get(target.position,{}).get("terrain","Clear")
    terrain_mod=TERRAIN_TO_HIT_MOD.get(target_terrain,0)
    hull_down_mod=-2 if hull_down else 0
    sf=_get_sf(target,facing)

    # Painting Laser Resolution (Affected by Target Facing Shield Factor)
    painting_hit,painting_roll=False,None
    if painting:
        if range_hexes>20:
            raise ValueError("Painting laser out of range (max 20 hexes)")
        # Target facing SF directly reduces the painting laser to-hit target number!
        p_mod=max(1,min(12,_base_to_hit(range_hexes)+terrain_mod+hull_down_mod - sf))
        painting_roll=random.randint(1,10)
        painting_hit=(painting_roll==1) or (painting_roll!=10 and painting_roll<=p_mod)

    # If painting laser succeeded, target shield factor is negated (0); otherwise full SF penalty applies
    effective_sf_mod=0 if painting_hit else -sf
    attacker_weapons=attacker.entity_profile.get('collections',{}).get('Weapons',[])
    eligible,blocked=[],{}

    for wname in weapon_names:
        matched=next((w for w in attacker_weapons
                      if wname.lower() in w.get('Name','').lower()
                      or w.get('Name','').lower() in wname.lower()),None)
        if not matched:
            blocked[wname]="Weapon not found on this vehicle"
            continue
            
        dmg = matched.get('Damage', 'N/A')
        if str(dmg).upper() in ['N/A', 'S', 'NONE', ''] and not any(k in matched.get('Name','').lower() for k in ['vulcan','pd']):
            blocked[wname]=f"Weapon {matched.get('Name')} has no offensive damage profile ({dmg})"
            continue
            
        w_rng=matched.get('Range','N/A')
        if w_rng!='N/A' and range_hexes>int(w_rng):
            blocked[matched['Name']]=f"Out of range ({range_hexes} > max {w_rng})"
            continue
            
        # Missile Ammunition Validation (Gauss and Lasers are unlimited)
        if 'TVLG' in matched['Name'].upper():
            if not hasattr(attacker,'tvlg_ammo'):
                attacker.tvlg_ammo=next((m['Count'] for m in attacker.entity_profile.get('collections',{}).get('Missiles',[]) if m['Type']=='TVLG'), 4)
            if attacker.tvlg_ammo<=0:
                raise ValueError(f"Cannot fire {matched['Name']}: no TVLG ammo remaining")
        elif 'SMLM' in matched['Name'].upper():
            if not hasattr(attacker,'smlm_ammo'):
                attacker.smlm_ammo=next((m['Count'] for m in attacker.entity_profile.get('collections',{}).get('Missiles',[]) if m['Type']=='SMLM'), 2)
            if attacker.smlm_ammo<=0:
                raise ValueError(f"Cannot fire {matched['Name']}: no SMLM ammo remaining")
                
        eligible.append(matched)

    shots=[]
    for w in eligible:
        sh_mod=effective_sf_mod if _shields_apply(w['Name']) else 0
        modified=max(1,min(12,_base_to_hit(range_hexes)+terrain_mod+hull_down_mod+sh_mod))
        roll=random.randint(1,10)
        hit=(roll==1) or (roll!=10 and roll<=modified)
        dmg_record={}
        if hit:
            dmg_record=_apply_damage(target,facing,w['Name'])
            if 'TVLG' in w['Name'].upper(): attacker.tvlg_ammo-=1
            if 'SMLM' in w['Name'].upper(): attacker.smlm_ammo-=1
            
        shots.append({
            "weapon":w['Name'],
            "base_to_hit":_base_to_hit(range_hexes),
            "modifiers":{"terrain":terrain_mod,"hull_down":hull_down_mod,"shield":sh_mod},
            "modified_to_hit":modified,
            "roll":roll,
            "hit":hit,
            "damage":dmg_record
        })

    return {
        "range":range_hexes,
        "facing":facing,
        "hull_down":hull_down,
        "painting_roll":painting_roll,
        "painting_hit":painting_hit,
        "sf_negated":painting_hit and sf>0,
        "target_sf":sf,
        "eligible_weapons":[w['Name'] for w in eligible],
        "blocked_weapons":blocked,
        "shots":shots
    }
"""

inject_mechanic("calculate_hex_range", calculate_hex_range_code)
inject_mechanic("check_los", check_los_code)
inject_mechanic("resolve_combat", resolve_combat_code)

print("  calculate_hex_range   : rhombus hex distance")
print("  check_los             : LOS check (smoke blocks)")
print("  resolve_combat        : template damage, internal damage, SF painting modifier, missile ammo")

