function xdu_race:control/check
execute unless score #request_ok xdu matches 1 run return 0
execute unless data storage xdu_race:state current{state:"IDLE"} run return 0
scoreboard players set #valid xdu 1
function xdu_race:validate_environment
execute unless score #valid xdu matches 1 run return 0
execute unless data storage xdu_race:request plan run return 0
function xdu_race:control/new_attempt with storage xdu_race:request plan
execute unless score #fresh xdu matches 1 run return 0
scoreboard players set #instance_ok xdu 1
execute if data storage xdu_race:config instance run function xdu_race:control/instance_check
execute unless score #instance_ok xdu matches 1 run return 0
execute store result score #size xdu run data get storage xdu_race:request plan.tracks
execute unless score #size xdu matches 6 run return 0
execute store result score #size xdu run data get storage xdu_race:request plan.roster
execute unless score #size xdu matches 1..17 run return 0
execute if entity @e[tag=w,tag=grandprix] run return 0
data modify storage xdu_race:scratch old set from storage xdu_race:state current
data modify storage xdu_race:state current set from storage xdu_race:request plan
data modify storage xdu_race:state current.revision set from storage xdu_race:scratch old.revision
data modify storage xdu_race:state current.boot_id set from storage xdu_race:scratch old.boot_id
scoreboard players set #native xdu 1
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/11/_initialize
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/11/buttons/red
function xdu_race:control/write_slot {index:0}
function xdu_race:control/write_slot {index:1}
function xdu_race:control/write_slot {index:2}
function xdu_race:control/write_slot {index:3}
function xdu_race:control/write_slot {index:4}
function xdu_race:control/write_slot {index:5}
scoreboard players set #native xdu 0
function xdu_race:validate
execute unless score #valid xdu matches 1 run function xdu_race:error
execute unless score #valid xdu matches 1 run return 0
data modify storage xdu_race:state current.state set value "PRESET_LOADED"
function xdu_race:control/ack
