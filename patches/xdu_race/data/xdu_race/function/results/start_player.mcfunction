$execute as @a[name=$(name),nbt={UUID:$(uuid_int)},tag=playing] run data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].started set value 1b
$execute as @a[name=$(name),nbt={UUID:$(uuid_int)},tag=playing] run data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].status set value "RACING"
