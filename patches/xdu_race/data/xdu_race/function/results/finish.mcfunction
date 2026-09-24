execute unless entity @s[tag=xdu_member] run return 0
execute unless data storage xdu_race:state current{state:"RUNNING"} run return 0
function xdu_race:results/context
execute store result storage xdu_race:scratch ctx.index int 1 run scoreboard players get @s xdu
function xdu_race:results/finish_player with storage xdu_race:scratch ctx
