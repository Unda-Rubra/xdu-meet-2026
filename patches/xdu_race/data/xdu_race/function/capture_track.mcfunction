data modify storage xdu_race:scratch track set value {id:0,tags:[]}
execute store result storage xdu_race:scratch track.id int 1 run scoreboard players get @s rNumber
data modify storage xdu_race:scratch track.tags set from entity @s Tags
execute if entity @s[tag=customtrack] run data modify storage xdu_race:scratch track.uuid set from entity @s UUID
data modify storage xdu_race:settings tracks append from storage xdu_race:scratch track
