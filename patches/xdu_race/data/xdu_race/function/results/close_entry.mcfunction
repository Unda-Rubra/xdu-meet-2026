$execute if data storage xdu_race:state current.tracks[$(track)].players[{index:$(index),finished:1b}] run return 0
$execute unless data storage xdu_race:state current.tracks[$(track)].players[{index:$(index),started:1b}] run return 0
$data modify storage xdu_race:scratch row set from storage xdu_race:state current.roster[$(index)]
$data modify storage xdu_race:scratch row.track set value $(track)
function xdu_race:results/close_player with storage xdu_race:scratch row
