function xdu_race:control/check
execute unless score #request_ok xdu matches 1 run return 0
execute unless data storage xdu_race:state current{state:"ARMED"} run return 0
function xdu_race:validate
execute unless score #valid xdu matches 1 run function xdu_race:error
execute unless score #valid xdu matches 1 run return 0
function xdu_race:access/refresh
execute store result score #online xdu if entity @a[tag=xdu_member]
execute store result score #required xdu run data get storage xdu_race:state current.roster
execute unless score #online xdu = #required xdu run return 0
tag @a[tag=xdu_member] remove afk
tag @a[tag=xdu_member] remove forcespectate
tag @a[tag=xdu_member] add playing
scoreboard players set @a[tag=xdu_member] afkTime 0
data modify storage xdu_race:state current.state set value "RUNNING"
scoreboard players set #gate xdu 1
scoreboard players set #native xdu 1
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/11/start_grand_prix
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/0/set_mode_ready
scoreboard players set @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] gameTime 0
scoreboard players set #native xdu 0
function xdu_race:control/ack
