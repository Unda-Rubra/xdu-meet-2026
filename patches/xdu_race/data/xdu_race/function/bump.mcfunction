execute store result score #rev xdu run data get storage xdu_race:state current.revision
scoreboard players add #rev xdu 1
execute store result storage xdu_race:state current.revision int 1 run scoreboard players get #rev xdu
