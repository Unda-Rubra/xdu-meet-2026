execute unless data storage xdu_race:state current{state:"CEREMONY"} run return 0
data modify storage xdu_race:state current.state set value "GP_FINISHED"
data modify storage xdu_race:state current.frozen set value 1b
tag @e[tag=w] remove grandprixloop
function xdu_race:bump
function xdu_race:archive with storage xdu_race:state current
