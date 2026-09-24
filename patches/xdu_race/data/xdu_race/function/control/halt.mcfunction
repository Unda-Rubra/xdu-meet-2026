function xdu_race:control/check
execute unless score #request_ok xdu matches 1 run return 0
scoreboard players set #gate xdu 0
data modify storage xdu_race:state current.halted set value 1b
function xdu_race:control/ack
