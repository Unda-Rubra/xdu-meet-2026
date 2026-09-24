execute if data storage xdu_race:state current{state:"ERROR"} run return 0
execute store result storage xdu_race:state current.ai_count int 1 if entity @e[tag=ai]
execute store result storage xdu_race:state current.ai_master_count int 1 if entity @e[tag=AImaster]
data modify storage xdu_race:state current.state set value "ERROR"
data modify storage xdu_race:state current.error set value "Invariant violation or interrupted attempt; operator review required"
scoreboard players set #gate xdu 0
scoreboard players set #native xdu 0
function xdu_race:bump
function xdu_race:archive
