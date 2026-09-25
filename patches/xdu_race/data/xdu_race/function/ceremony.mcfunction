execute unless data storage xdu_race:state current{state:"RUNNING"} run return 0
data modify storage xdu_race:state current.state set value "CEREMONY"
data modify storage xdu_race:scratch queue set from storage xdu_race:state current.roster
data modify storage xdu_race:state current.results set value {}
function xdu_race:collect
function xdu_race:bump
