$execute as @a[name=$(name),nbt={UUID:$(uuid_int)}] store result storage xdu_race:state current.tracks[$(track)].players[$(index)].native_total int 1 run scoreboard players get @s gpPoints
$execute if entity @a[name=$(name),nbt={UUID:$(uuid_int)}] run data modify storage xdu_race:state current.tracks[$(track)].players[$(index)].native_commit_observed set value 1b
