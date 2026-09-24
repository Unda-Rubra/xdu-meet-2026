scoreboard players set #launch_ok xdu 0
execute unless score #gate xdu matches 1 run return 0
execute if data storage xdu_race:state current{halted:1b} run return 0
scoreboard players set #safe xdu 0
execute if data storage xdu_race:state current{state:"RUNNING"} run scoreboard players set #safe xdu 1
execute if data storage xdu_race:state current{state:"BETWEEN_TRACKS"} run scoreboard players set #safe xdu 1
execute unless score #safe xdu matches 1 run return 0
execute unless score @s gpRound matches 1..6 run function xdu_race:error
execute unless score @s gpRound matches 1..6 run return 0
function xdu_race:validate
execute unless score #valid xdu matches 1 run function xdu_race:error
execute unless score #valid xdu matches 1 run return 0
execute store result score #previous xdu run data get storage xdu_race:state current.track_index
scoreboard players add #previous xdu 1
execute unless score @s gpRound = #previous xdu run function xdu_race:error
execute unless score @s gpRound = #previous xdu run return 0
execute store result storage xdu_race:state current.track_index int 1 run scoreboard players get @s gpRound
data modify storage xdu_race:state current.state set value "RUNNING"
function xdu_race:access/refresh
tag @a[tag=xdu_member] remove forcespectate
tag @a[tag=xdu_member] remove afk
tag @a[tag=xdu_member] add playing
scoreboard players set @a[tag=xdu_member] afkTime 0
function xdu_race:bump
scoreboard players set #racepermit xdu 1
scoreboard players set #launch_ok xdu 1
