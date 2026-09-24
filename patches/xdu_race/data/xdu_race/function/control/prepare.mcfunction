function xdu_race:control/check
execute unless score #request_ok xdu matches 1 run return 0
execute unless data storage xdu_race:state current{state:"PRESET_LOADED"} run return 0
function xdu_race:validate
execute unless score #valid xdu matches 1 run function xdu_race:error
execute unless score #valid xdu matches 1 run return 0
function xdu_race:access/refresh
execute store result score #online xdu if entity @a[tag=xdu_member]
execute store result score #required xdu run data get storage xdu_race:state current.roster
execute unless score #online xdu = #required xdu run return 0
tag @a[tag=xdu_member] remove forcespectate
tag @a[tag=xdu_member] remove afk
tag @a[tag=xdu_member] add playing
scoreboard players set @a[tag=xdu_member] afkTime 0
data modify storage xdu_race:state current.state set value "ARMED"
function xdu_race:control/ack
