function xdu_race:control/check
execute unless score #request_ok xdu matches 1 run return 0
execute unless data storage xdu_race:request {archive_verified:1b} run return 0
scoreboard players set #safe xdu 0
execute if data storage xdu_race:state current{state:"GP_FINISHED"} run scoreboard players set #safe xdu 1
execute if data storage xdu_race:state current{state:"STOPPED"} run scoreboard players set #safe xdu 1
execute unless score #safe xdu matches 1 run return 0
function xdu_race:archive
scoreboard players set #native xdu 1
execute as @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s if score @s gameState matches 4 run function sprint_racer:game_logic/4/end
scoreboard players set #native xdu 0
data modify storage xdu_race:state current.reset_receipt_hash set from storage xdu_race:request archive_snapshot_hash
data modify storage xdu_race:state current.state set value "IDLE"
data remove storage xdu_race:state current.tracks
data modify storage xdu_race:state current.roster set value []
data modify storage xdu_race:state current.track_index set value 0
data remove storage xdu_race:state current.halted
function xdu_race:control/ack
