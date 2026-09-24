tag @a remove xdu_lobby_operator
tag @a remove admin
data remove storage xdu_lobby:state ready
execute in minecraft:overworld run forceload add 1536 336 1695 479
schedule function xdu_lobby:initialize 3s replace
