$data modify storage xdu_race:scratch row set from storage xdu_race:state current.roster[$(index)]
$data modify storage xdu_race:scratch row.track set value $(track)
function xdu_race:results/start_player with storage xdu_race:scratch row
