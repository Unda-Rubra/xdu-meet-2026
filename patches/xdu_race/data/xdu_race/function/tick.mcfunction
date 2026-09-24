tag @a[tag=admin] remove admin
tag @a[tag=tournament_admin] remove tournament_admin
scoreboard players set @a adminMode 0
scoreboard players add #tick xdu 1
execute unless score #tick xdu matches 20.. run return 0
scoreboard players set #tick xdu 0
function xdu_race:access/refresh
execute if entity @e[tag=ai] run function xdu_race:error
execute if entity @e[tag=AImaster] run function xdu_race:error
