data modify storage xdu_race:config main_lobby set value 1b
tag @a remove admin
data remove storage xdu_lobby:state ready
execute in minecraft:overworld run forceload add 1536 336 1695 479
schedule function xdu_lobby:initialize 3s replace
