execute unless data storage xdu_race:state current{state:"RUNNING"} run return 0
execute store result storage xdu_race:state current.track_index int 1 run scoreboard players get @s gpRound
function xdu_race:bump
