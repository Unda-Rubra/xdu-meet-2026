execute if data storage xdu_race:config {main_lobby:1b} run return 0
tag @a[tag=!xdu_member] add forcespectate
tag @a[tag=!xdu_member] remove playing
gamemode spectator @a[tag=xdu_admin]
tag @a[tag=xdu_admin] remove playing
tag @a[tag=xdu_admin] remove xdu_member
scoreboard players reset @a[tag=xdu_admin] gpPoints
scoreboard players reset @a[tag=xdu_admin] points
scoreboard players reset @a[tag=xdu_admin] dummyPoints
