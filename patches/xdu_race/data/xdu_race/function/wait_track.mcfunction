execute unless data storage xdu_race:state current{state:"RUNNING"} run return 0
data modify storage xdu_race:state current.state set value "WAITING"
gamemode spectator @a
tellraw @a {"text":"本组已完成本图，等待其他组；所有启用组就绪后一起继续。","color":"yellow"}
function xdu_race:bump
