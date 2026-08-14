"""
test_centurion_combat.py
========================
Combat Phase test suite for the Centurion simulation engine.

Tests TC1-TC9 call resolve_combat directly via the seeded mechanic.
All rules sourced from the Renegade Legion RAG-Doll:
  - Roll 1d10; hit if <= modified to-hit number. 1=auto-hit, 10=auto-miss.
  - Range->to-hit: 1=12, 2-3=11, 4-6=10, 7-10=9, 11-15=8, 16-20=7, off-board=6
  - Terrain mod: Light Woods -1, Heavy Woods/Smoke -2
  - Shield Factor (SF) reduces to-hit for lasers/missiles; Gauss NOT affected
  - Painting laser: separate roll; if hit -> negates SF for all friendly attacks this turn
  - Hull down: -2 to-hit; all hits resolve against Turret armor grid
  - Smoke in LOS: LOS blocked -> ValueError raised
  - Missiles: same to-hit rules as direct fire
"""

import sys
import types
import pytest

sys.path.insert(0, '.')

# ── Load engine and seeded combat mechanics from SQL cache ───
from engine.simulation.dynamic_engine import DynamicEngine

_engine = DynamicEngine('combat_test')
_arbiter = _engine.arbiter

_resolve_combat = _arbiter.get_or_generate_mechanic(
    'resolve_combat', 'combat resolution to-hit table shields terrain painting facing damage')
_check_los = _arbiter.get_or_generate_mechanic(
    'check_los', 'line of sight smoke blocking')
_hex_range = _arbiter.get_or_generate_mechanic(
    'calculate_hex_range', 'hex distance range calculation')


# ── Minimal stubs for CenturionUnit / WorldStateManager ─────

class MockDamageState:
    def __init__(self, armor_grids):
        self.armor_grids = armor_grids

class MockUnit:
    """Minimal unit stub for combat resolution tests."""
    def __init__(self, uid, position, heading, entity_name):
        self.id       = uid
        self.position = position
        self.heading  = heading          # 1-6 (1=N, 2=NE, 3=SE, 4=S, 5=SW, 6=NW)
        self.hull_down = False

        engine = DynamicEngine('probe')
        self.entity_profile = engine.rules.get_entity_data(entity_name)

        # Build armor grids from profile data
        armor = {}
        for grid_name, gd in self.entity_profile.get('grids', {}).items():
            if 'Depth' in gd:
                depth = gd['Depth']
                width = gd.get('Width', 10)
                armor[grid_name] = [depth] * width
        self.damage_state = MockDamageState(armor)

class MockWorldState:
    def __init__(self):
        self.map_hexes = {}  # hex_id -> {"terrain": str}

class MockWSM:
    """Minimal WorldStateManager stub."""
    def __init__(self, hexes=None):
        self._state = MockWorldState()
        if hexes:
            self._state.map_hexes = hexes

    def get_state(self):
        return self._state

    def set_terrain(self, hex_id, terrain):
        self._state.map_hexes[hex_id] = {"terrain": terrain}


# ── Helpers ──────────────────────────────────────────────────

def setup_duel(lib_pos, hor_pos, lib_heading=4, hor_heading=1, hexes=None):
    """Build a Liberator vs Horatius pair with an optional hex terrain map."""
    lib = MockUnit('lib1', lib_pos, lib_heading, 'rl_liberator_medium_grav_tank')
    hor = MockUnit('hor1', hor_pos, hor_heading, 'tog_horatius_medium_grav_tank')
    wsm = MockWSM(hexes or {})
    return lib, hor, wsm


# ════════════════════════════════════════════════════════════════
# TC1  Range >= 16: only laser in range; Gauss and TVLG blocked
# ════════════════════════════════════════════════════════════════
def test_tc1_long_range_laser_only():
    """
    Liberator (0101) vs Horatius (0120) = 19 hexes.
    At this range only the 5/6 Laser (max 20) is eligible.
    50mm Gauss (max 6) and TVLG(4) (max 6) are out of range.
    """
    lib, hor, wsm = setup_duel('0101', '0120')
    r = _resolve_combat(lib, hor, wsm,
                        '[FIRE: Target=hor1, Weapons=5/6 Laser;50mm;TVLG(4), Painting=True]',
                        seed=42)

    assert r['range'] == 19
    assert '5/6 Laser' in r['eligible_weapons'],  f"Laser should be eligible: {r}"
    assert '50mm' not in r['eligible_weapons'],    f"Gauss out of range at 19: {r}"
    assert 'TVLG(4)' not in r['eligible_weapons'], f"TVLG out of range at 19: {r}"
    assert '50mm' in r['blocked_weapons'] or 'TVLG(4)' in r['blocked_weapons']


# ════════════════════════════════════════════════════════════════
# TC2  Range <= 15: all weapons eligible
# ════════════════════════════════════════════════════════════════
def test_tc2_medium_range_all_weapons():
    """
    Liberator (0101) vs Horatius (0106) = 5 hexes (range band 4-6, base to-hit 10).
    All three weapons eligible: 5/6 Laser, 50mm, TVLG(4).
    """
    lib, hor, wsm = setup_duel('0101', '0106')
    r = _resolve_combat(lib, hor, wsm,
                        '[FIRE: Target=hor1, Weapons=5/6 Laser;50mm;TVLG(4), Painting=True]',
                        seed=42)

    assert r['range'] == 5
    assert '5/6 Laser' in r['eligible_weapons']
    assert '50mm'    in r['eligible_weapons']
    assert 'TVLG(4)' in r['eligible_weapons']
    # Base to-hit at range 5 is 10
    laser_shot = next(s for s in r['shots'] if s['weapon'] == '5/6 Laser')
    assert laser_shot['base_to_hit'] == 10


# ════════════════════════════════════════════════════════════════
# TC3  Missile range: TVLG fires + SMLM defensive intercept
# ════════════════════════════════════════════════════════════════
def test_tc3_missile_fire_and_defensive():
    """
    Lib (0101) vs Hor (0106) = 5 hexes, within TVLG range (max 6).
    Attack: Lib fires TVLG missile.
    Defensive: Hor fires SMLM at incoming TVLG.
    Missiles use same to-hit rules as direct fire.
    """
    lib, hor, wsm = setup_duel('0101', '0106')
    # Lib fires TVLG
    r_atk = _resolve_combat(lib, hor, wsm,
                            '[FIRE: Target=hor1, Weapons=TVLG(4), Painting=False]',
                            seed=7)
    assert 'TVLG(4)' in r_atk['eligible_weapons']
    tvlg_shot = r_atk['shots'][0]
    assert tvlg_shot['weapon'] == 'TVLG(4)'
    assert tvlg_shot['base_to_hit'] == 10  # range 5, band 4-6

    # Hor defensive SMLM fire at incoming missile
    # SMLM range 10 (from Horatius profile); target is the lib at range 5 < 10
    r_def = _resolve_combat(hor, lib, wsm,
                            '[FIRE: Target=lib1, Weapons=SMLM (2), Painting=False]',
                            seed=8)
    assert 'SMLM (2)' in r_def['eligible_weapons']
    smlm_shot = r_def['shots'][0]
    assert smlm_shot['base_to_hit'] == 10  # same range band
    # Verify ammo was consumed
    assert hasattr(hor, 'smlm_ammo') and hor.smlm_ammo == 0  # started with 1 round, fired 1


# ════════════════════════════════════════════════════════════════
# TC4  Hull down: all hits go to Turret armor
# ════════════════════════════════════════════════════════════════
def test_tc4_hull_down_turret_only():
    """
    Hor (0106) is hull down.
    - -2 to-hit modifier applied (harder to hit)
    - All hits resolved against 'Turret Armor' regardless of facing
    """
    lib, hor, wsm = setup_duel('0101', '0106')
    hor.hull_down = True

    # Record initial turret armor
    turret_before = list(hor.damage_state.armor_grids.get('Turret Armor', []))
    front_before  = list(hor.damage_state.armor_grids.get('Front Armor', []))

    # Force a hit by using seed that produces roll=1 (auto-hit)
    r = _resolve_combat(lib, hor, wsm,
                        '[FIRE: Target=hor1, Weapons=5/6 Laser, Painting=False]',
                        seed=1)

    assert r['hull_down'] is True
    assert r['facing'] == 'Turret', f"Hull down should force Turret facing, got {r['facing']}"
    # Hull-down mod should be -2
    laser_shot = r['shots'][0]
    assert laser_shot['modifiers']['hull_down'] == -2, f"Expected -2 hull_down mod: {laser_shot}"

    if laser_shot['hit']:
        # Front/Side/Stern armor is untouched; all damage routes to Turret facing
        front_after = hor.damage_state.armor_grids.get('Front Armor', [])
        assert sum(front_after) == sum(front_before), "Front armor must be untouched when hull down"
        # Turret Armor Depth=0 on this SSD (Turret Internals take the hit).
        # The key assertion is the damage record reports 'Turret Armor' grid.
        dmg = laser_shot['damage']
        if dmg:
            assert dmg.get('grid') == 'Turret Armor', \
                f"Hull-down damage must route to Turret Armor grid, got: {dmg.get('grid')}"


# ════════════════════════════════════════════════════════════════
# TC5  Smoke blocks LOS to one target
# ════════════════════════════════════════════════════════════════
def test_tc5_smoke_blocks_los():
    """
    Two enemy vehicles. One has smoke between it and the Liberator.
    Can fire at the clear target; smoke target raises ValueError.
    """
    lib_pos  = '0101'
    hor1_pos = '0106'  # clear path (5 hexes south)
    hor2_pos = '0110'  # smoke at 0108 blocks LOS

    smoke_hex = '0108'
    wsm = MockWSM({smoke_hex: {"terrain": "Smoke"}})

    lib  = MockUnit('lib1',  lib_pos,  4, 'rl_liberator_medium_grav_tank')
    hor1 = MockUnit('hor1',  hor1_pos, 1, 'tog_horatius_medium_grav_tank')
    hor2 = MockUnit('hor2',  hor2_pos, 1, 'tog_horatius_medium_grav_tank')

    # Can fire at hor1 (clear LOS)
    r = _resolve_combat(lib, hor1, wsm,
                        '[FIRE: Target=hor1, Weapons=5/6 Laser, Painting=False]',
                        seed=42)
    assert '5/6 Laser' in r['eligible_weapons']

    # Cannot fire at hor2 (smoke at 0108 is on the LOS)
    with pytest.raises(ValueError, match="blocks LOS"):
        _resolve_combat(lib, hor2, wsm,
                        '[FIRE: Target=hor2, Weapons=5/6 Laser, Painting=False]',
                        seed=42)


# ════════════════════════════════════════════════════════════════
# TC6  Target in light woods: -1 to-hit modifier
# ════════════════════════════════════════════════════════════════
def test_tc6_light_woods_modifier():
    """
    Hor is in a Light Woods hex.
    Terrain mod = -1 applied to the to-hit number.
    """
    hor_pos = '0106'
    wsm = MockWSM({hor_pos: {"terrain": "Light Woods"}})
    lib, hor, _ = setup_duel('0101', hor_pos)
    lib._wsm = wsm

    r = _resolve_combat(lib, hor, wsm,
                        '[FIRE: Target=hor1, Weapons=5/6 Laser, Painting=False]',
                        seed=42)

    laser_shot = r['shots'][0]
    assert laser_shot['modifiers']['terrain'] == -1, f"Expected -1 terrain mod: {laser_shot}"
    # Base 10 (range 5) + terrain -1 = modified 9
    assert laser_shot['modified_to_hit'] <= 9, f"Expected modified <= 9: {laser_shot}"


# ════════════════════════════════════════════════════════════════
# TC7  Target facing backward: hits go to Stern armor
# ════════════════════════════════════════════════════════════════
def test_tc7_target_facing_backward():
    """
    Lib at 0101 (heading=4, facing south).
    Hor at 0106 with heading=4 (facing south, i.e. AWAY from attacker).
    Attacker is to the north of the target -> Stern facing.
    """
    lib, hor, wsm = setup_duel('0101', '0106', lib_heading=4, hor_heading=4)
    # lib is north of hor; hor heading=4 (south) means its stern faces north
    r = _resolve_combat(lib, hor, wsm,
                        '[FIRE: Target=hor1, Weapons=5/6 Laser, Painting=False]',
                        seed=42)

    assert r['facing'] == 'Stern', f"Target facing south, attacker from north -> Stern, got {r['facing']}"

    # Verify damage hits Stern Armor if there was a hit
    if r['shots'] and r['shots'][0]['hit']:
        dmg = r['shots'][0]['damage']
        assert dmg.get('grid') == 'Stern Armor', f"Damage should be to Stern Armor: {dmg}"


# ════════════════════════════════════════════════════════════════
# TC8  TVLG ammo depleted: ValueError raised
# ════════════════════════════════════════════════════════════════
def test_tc8_tvlg_ammo_depleted():
    """
    Liberator has tvlg_ammo = 0.
    Attempting to fire TVLG raises ValueError.
    """
    lib, hor, wsm = setup_duel('0101', '0106')
    lib.tvlg_ammo = 0  # manually deplete

    with pytest.raises(ValueError, match="no TVLG ammo remaining"):
        _resolve_combat(lib, hor, wsm,
                        '[FIRE: Target=hor1, Weapons=TVLG(4), Painting=False]',
                        seed=42)


# ════════════════════════════════════════════════════════════════
# TC9  Two Liberators firing on same target: damage stacks
# ════════════════════════════════════════════════════════════════
def test_tc9_two_attackers_same_target():
    """
    Two Liberators firing on the same Horatius.
    Damage is cumulative; armor depletes across both shots.
    """
    lib1 = MockUnit('lib1', '0101', 4, 'rl_liberator_medium_grav_tank')
    lib2 = MockUnit('lib2', '0201', 3, 'rl_liberator_medium_grav_tank')  # from NE-ish
    hor  = MockUnit('hor1', '0106', 1, 'tog_horatius_medium_grav_tank')
    wsm  = MockWSM()

    front_before = list(hor.damage_state.armor_grids.get('Front Armor', []))
    total_before = sum(front_before)

    r1 = _resolve_combat(lib1, hor, wsm,
                         '[FIRE: Target=hor1, Weapons=5/6 Laser, Painting=False]',
                         seed=1)
    r2 = _resolve_combat(lib2, hor, wsm,
                         '[FIRE: Target=hor1, Weapons=5/6 Laser, Painting=False]',
                         seed=2)

    # Both resolved cleanly
    assert '5/6 Laser' in r1['eligible_weapons']
    assert '5/6 Laser' in r2['eligible_weapons']

    # If either hit, total armor < before
    total_hits = sum(1 for r in [r1, r2] for s in r['shots'] if s['hit'])
    if total_hits:
        total_armor = sum(hor.damage_state.armor_grids.get('Front Armor', []) +
                          hor.damage_state.armor_grids.get('Stern Armor', []) +
                          hor.damage_state.armor_grids.get('Turret Armor', []))
        assert total_armor < total_before + sum(hor.damage_state.armor_grids.get('Stern Armor',[])) + sum(hor.damage_state.armor_grids.get('Turret Armor',[])), \
               "Expected cumulative damage on target"


# ════════════════════════════════════════════════════════════════
# Helpers: standalone range & LOS tests
# ════════════════════════════════════════════════════════════════
def test_hex_range_straight():
    assert _hex_range('0101', '0106') == 5   # straight south
    assert _hex_range('0101', '0120') == 19  # 19 hexes south
    assert _hex_range('0101', '0101') == 0   # same hex

def test_hex_range_diagonal():
    assert _hex_range('0101', '0606') == 5   # 5 SE
    assert _hex_range('0601', '0106') == 10  # opposite-sign: 5+5

def test_los_clear():
    wsm = MockWSM()
    clear, reason = _check_los('0101', '0106', wsm)
    assert clear

def test_los_blocked_by_smoke():
    wsm = MockWSM({'0104': {'terrain': 'Smoke'}})
    clear, reason = _check_los('0101', '0106', wsm)
    assert not clear
    assert 'Smoke' in reason


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
