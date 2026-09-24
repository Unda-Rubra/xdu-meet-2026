$execute if data storage xdu_race:state current.tracks[{index:$(track),settled:1b}] run return 0
$execute unless data storage xdu_race:state current.tracks[{index:$(track),closed:1b,commit_phase_reached:1b}] run function xdu_race:error
$execute unless data storage xdu_race:state current.tracks[{index:$(track),closed:1b,commit_phase_reached:1b}] run return 0
$data modify storage xdu_race:state current.tracks[$(track)].settled set value 1b
data modify storage xdu_race:state current.state set value "BETWEEN_TRACKS"
execute if data storage xdu_race:state current{track_index:6} run function xdu_race:results/freeze
function xdu_race:bump
function xdu_race:archive
