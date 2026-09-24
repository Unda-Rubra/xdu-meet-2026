execute store result score #track_index xdu run data get storage xdu_race:state current.track_index
scoreboard players remove #track_index xdu 1
execute store result storage xdu_race:scratch ctx.track int 1 run scoreboard players get #track_index xdu
