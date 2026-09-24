scoreboard players set #valid xdu 1
function xdu_race:validate_environment
execute store result score #anchors xdu if entity @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1]
execute unless score #anchors xdu matches 1 run scoreboard players set #valid xdu 0
execute unless entity @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1,tag=optRAInever] run scoreboard players set #valid xdu 0
execute unless score @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] optRAIcount matches 0 run scoreboard players set #valid xdu 0
execute if entity @e[tag=ai] run scoreboard players set #valid xdu 0
execute if entity @e[tag=AImaster] run scoreboard players set #valid xdu 0
execute if entity @e[tag=w,tag=grandprixloop] run scoreboard players set #valid xdu 0
execute if entity @e[tag=w,tag=endlessMode] run scoreboard players set #valid xdu 0
execute unless score @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] gamemodePresetA matches 1 run scoreboard players set #valid xdu 0
execute if entity @e[tag=w,tag=teamplay] run scoreboard players set #valid xdu 0
execute if data storage xdu_race:state current.tracks run function xdu_race:validate_slots
execute if data storage xdu_race:state current.tracks unless data storage xdu_race:state current.settings_summary run scoreboard players set #valid xdu 0
execute if data storage xdu_race:state current.settings_summary run function xdu_race:settings/validate
