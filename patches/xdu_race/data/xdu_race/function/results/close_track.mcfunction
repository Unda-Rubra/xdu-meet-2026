$execute if data storage xdu_race:state current.tracks[{index:$(track),closed:1b}] run return 0
$data modify storage xdu_race:state current.tracks[$(track)].closed set value 1b
$execute store result storage xdu_race:state current.tracks[$(track)].closed_at_tick long 1 run time query gametime
$execute if data storage xdu_race:state current.roster[0] run function xdu_race:results/close_entry {track:$(track),index:0}
$execute if data storage xdu_race:state current.roster[1] run function xdu_race:results/close_entry {track:$(track),index:1}
$execute if data storage xdu_race:state current.roster[2] run function xdu_race:results/close_entry {track:$(track),index:2}
$execute if data storage xdu_race:state current.roster[3] run function xdu_race:results/close_entry {track:$(track),index:3}
$execute if data storage xdu_race:state current.roster[4] run function xdu_race:results/close_entry {track:$(track),index:4}
$execute if data storage xdu_race:state current.roster[5] run function xdu_race:results/close_entry {track:$(track),index:5}
$execute if data storage xdu_race:state current.roster[6] run function xdu_race:results/close_entry {track:$(track),index:6}
$execute if data storage xdu_race:state current.roster[7] run function xdu_race:results/close_entry {track:$(track),index:7}
$execute if data storage xdu_race:state current.roster[8] run function xdu_race:results/close_entry {track:$(track),index:8}
$execute if data storage xdu_race:state current.roster[9] run function xdu_race:results/close_entry {track:$(track),index:9}
$execute if data storage xdu_race:state current.roster[10] run function xdu_race:results/close_entry {track:$(track),index:10}
$execute if data storage xdu_race:state current.roster[11] run function xdu_race:results/close_entry {track:$(track),index:11}
$execute if data storage xdu_race:state current.roster[12] run function xdu_race:results/close_entry {track:$(track),index:12}
$execute if data storage xdu_race:state current.roster[13] run function xdu_race:results/close_entry {track:$(track),index:13}
$execute if data storage xdu_race:state current.roster[14] run function xdu_race:results/close_entry {track:$(track),index:14}
$execute if data storage xdu_race:state current.roster[15] run function xdu_race:results/close_entry {track:$(track),index:15}
$execute if data storage xdu_race:state current.roster[16] run function xdu_race:results/close_entry {track:$(track),index:16}
function xdu_race:bump
function xdu_race:archive
