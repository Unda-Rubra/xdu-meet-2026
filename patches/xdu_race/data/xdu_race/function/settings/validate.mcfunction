execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] run function xdu_race:settings/capture
data modify storage xdu_race:scratch expected set from storage xdu_race:state current.settings_summary
execute store success score #changed xdu run data modify storage xdu_race:scratch expected set from storage xdu_race:scratch settings
execute if score #changed xdu matches 1 run scoreboard players set #valid xdu 0
