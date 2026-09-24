$data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].status set value "DISCONNECTED"
$execute if entity @a[name=$(name),nbt={UUID:$(uuid_int)}] run data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].status set value "UNFINISHED"
