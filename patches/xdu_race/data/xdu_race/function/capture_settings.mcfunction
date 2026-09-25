data modify storage xdu_race:settings blocks set value []
data modify storage xdu_race:settings tracks set value []
execute as @e[type=armor_stand,tag=trackStandR] run function xdu_race:capture_track
execute as @e[type=armor_stand,tag=trackStandB] run function xdu_race:capture_track
data modify storage xdu_race:scratch cursor set value {x:1584,y:39,z:373}
scoreboard players set #captureX xdu 1584
scoreboard players set #captureZ xdu 373
function xdu_race:capture_grid
