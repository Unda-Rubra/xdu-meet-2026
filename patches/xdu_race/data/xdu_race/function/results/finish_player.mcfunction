$execute if data storage xdu_race:state current.tracks[{index:$(track),closed:1b}] run return 0
$execute unless data storage xdu_race:state current.tracks[$(track)].players[{index:$(index),started:1b,finished:0b}] run return 0
$data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].finished set value 1b
$data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].status set value "FINISHED"
$execute store result storage xdu_race:state current.tracks[$(track)].players[$(index)].finish_pos_raw int 1 run scoreboard players get @s finishPos
$execute store result storage xdu_race:state current.tracks[$(track)].players[$(index)].award int 1 run scoreboard players get @s addPoints
$execute store result storage xdu_race:state current.tracks[$(track)].players[$(index)].time_minutes int 1 run scoreboard players get @s storedTimeMin
$execute store result storage xdu_race:state current.tracks[$(track)].players[$(index)].time_seconds int 1 run scoreboard players get @s storedTimeSec
$execute store result storage xdu_race:state current.tracks[$(track)].players[$(index)].time_milliseconds int 1 run scoreboard players get @s storedTimeMsec
$execute store result storage xdu_race:state current.tracks[$(track)].players[$(index)].finished_at_tick long 1 run time query gametime
function xdu_race:bump
function xdu_race:archive
