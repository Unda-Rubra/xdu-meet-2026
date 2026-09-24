function xdu_race:control/check
execute unless score #request_ok xdu matches 1 run return 0
execute unless data storage xdu_race:state current{halted:1b} run return 0
execute unless data storage xdu_race:request {archive_verified:1b} run return 0
execute if data storage xdu_race:state current{state:"GP_FINISHED"} run return 0
data modify storage xdu_race:state current.state set value "STOPPED"
schedule clear sprint_racer:game_logic/1/check_for_lone_player
scoreboard players set #native xdu 1
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s if entity @s[tag=grandprix] run function sprint_racer:game_logic/11/cancel_grand_prix
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s if score @s gameState matches 11 run function sprint_racer:game_logic/11/exit
scoreboard players set #native xdu 0
function xdu_race:control/ack
