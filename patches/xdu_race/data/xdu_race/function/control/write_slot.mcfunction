$execute store result score #track xdu run data get storage xdu_race:state current.tracks[$(index)].native_id
scoreboard players operation @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] worldmapID = #track xdu
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/11/choose_track
