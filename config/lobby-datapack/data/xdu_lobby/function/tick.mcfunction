execute unless data storage xdu_lobby:state {ready:1b} run return 0
tag @a[tag=!xdu_admin] remove admin
tag @a[tag=xdu_admin] add admin
scoreboard players set @a[tag=!xdu_admin] adminMode 0
scoreboard players set @a[tag=xdu_admin] adminMode 1
tag @a remove readyup
scoreboard players set @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1] readyState 0
bossbar set minecraft:readyprogress players
bossbar set minecraft:menutimer players
scoreboard objectives setdisplay sidebar
execute as @a[tag=!xdu_lobby_placed] run function xdu_lobby:join
