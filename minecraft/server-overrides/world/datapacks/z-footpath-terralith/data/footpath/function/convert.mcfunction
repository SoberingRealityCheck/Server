# Do not convert if anything other than air or a snow layer sits above the target.
# This leaves blocks under fences, leaves, flowers, etc. untouched.
execute unless block ~ ~0 ~ #minecraft:air unless block ~ ~0 ~ minecraft:snow run return 0

# ============================================================
# BLOCK CONVERSION RULES
# Add new swap pairs here following the same pattern.
# Each rule uses "return run" so only ONE conversion fires per
# threshold event — preventing instant chain-skipping.
# Also add any new source blocks to tags/block/convertible.json
# and new toggles to dialog/main.json, load.mcfunction, apply.mcfunction.
# ============================================================

# --- GRASS PATH (toggle: #grass fp.settings) ---
# Step 1: Grass Block -> Dirt
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:grass_block run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:grass_block
# Step 2: Dirt -> Dirt Path
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:dirt run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt_path replace minecraft:dirt

# --- STONE PATH (toggle: #stone fp.settings) ---
# Step 1: Stone -> Cobblestone
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:stone run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobblestone replace minecraft:stone
# Step 2: Cobblestone -> Mossy Cobblestone
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:cobblestone run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:mossy_cobblestone replace minecraft:cobblestone

# --- COARSE DIRT -> DIRT (toggle: #coarse_dirt fp.settings) ---
execute if score #coarse_dirt fp.settings matches 1 if block ~ ~-1 ~ minecraft:coarse_dirt run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:coarse_dirt

# --- DEEPSLATE -> COBBLED DEEPSLATE (toggle: #deepslate fp.settings) ---
execute if score #deepslate fp.settings matches 1 if block ~ ~-1 ~ minecraft:deepslate run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobbled_deepslate replace minecraft:deepslate

# --- MYCELIUM -> DIRT (toggle: #mycelium fp.settings) ---
execute if score #mycelium fp.settings matches 1 if block ~ ~-1 ~ minecraft:mycelium run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:mycelium

# --- NYLIUM -> NETHERRACK (toggle: #nylium fp.settings) ---
execute if score #nylium fp.settings matches 1 if block ~ ~-1 ~ minecraft:crimson_nylium run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:netherrack replace minecraft:crimson_nylium
execute if score #nylium fp.settings matches 1 if block ~ ~-1 ~ minecraft:warped_nylium run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:netherrack replace minecraft:warped_nylium

# --- PODZOL -> DIRT (toggle: #podzol fp.settings) ---
execute if score #podzol fp.settings matches 1 if block ~ ~-1 ~ minecraft:podzol run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:podzol

# --- SAND -> SANDSTONE (toggle: #sand fp.settings) ---
execute if score #sand fp.settings matches 1 if block ~ ~-1 ~ minecraft:sand run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:sandstone replace minecraft:sand

# --- RED SAND -> RED SANDSTONE (toggle: #red_sand fp.settings) ---
execute if score #red_sand fp.settings matches 1 if block ~ ~-1 ~ minecraft:red_sand run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:red_sandstone replace minecraft:red_sand

# ============================================================
# TERRALITH EXTENSION (z-footpath-terralith)
# This file replaces footpath:convert whole -- functions do not merge --
# so everything above is a verbatim copy of the base pack's rules and
# everything below is new. If the base pack updates convert.mcfunction,
# re-copy it here or these rules will silently use the old version.
#
# New rules reuse the base toggles (#grass, #stone) so the in-game
# settings dialog still switches them. They also chain into the base
# rules: gravel -> coarse dirt -> dirt -> dirt path.
#
# Left alone on purpose: terracotta, snow, ice. Hard ground and weather
# that heals itself, not worn paths.
# ============================================================

# --- LOOSE / SOFT GROUND (toggle: #grass) ---
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:gravel run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:coarse_dirt replace minecraft:gravel
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:clay run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:coarse_dirt replace minecraft:clay
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:rooted_dirt run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:rooted_dirt
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:moss_block run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:moss_block
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:mud run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:packed_mud replace minecraft:mud
execute if score #grass fp.settings matches 1 if block ~ ~-1 ~ minecraft:packed_mud run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:dirt replace minecraft:packed_mud

# --- HARD STONE (toggle: #stone) ---
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:granite run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobblestone replace minecraft:granite
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:diorite run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobblestone replace minecraft:diorite
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:andesite run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobblestone replace minecraft:andesite
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:calcite run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:tuff replace minecraft:calcite
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:tuff run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:gravel replace minecraft:tuff
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:blackstone run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobbled_deepslate replace minecraft:blackstone
execute if score #stone fp.settings matches 1 if block ~ ~-1 ~ minecraft:smooth_basalt run return run fill ~ ~-1 ~ ~ ~-1 ~ minecraft:cobbled_deepslate replace minecraft:smooth_basalt

return 0
