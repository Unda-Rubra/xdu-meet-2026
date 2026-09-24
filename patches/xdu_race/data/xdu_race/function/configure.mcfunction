execute unless entity @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] run schedule function xdu_race:configure 3s replace
execute unless entity @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] run return 0
execute as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function xdu_race:configure_world
