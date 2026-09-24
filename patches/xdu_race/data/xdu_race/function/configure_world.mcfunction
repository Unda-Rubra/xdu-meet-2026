execute if data storage xdu_race:state current{state:"RUNNING"} run return 0
scoreboard players set @s adminMode 1
tag @s add requireAdmin
scoreboard players set @s optRAIcount 0
tag @s add optRAInever
tag @s remove optRAIsingle
tag @s remove optRAIalways
tag @s remove RAIautocount
tag @s remove grandprixloop
tag @s remove endlessMode
tag @s remove randomPresetA
scoreboard players set @s gamemodePresetA 1
tag @s remove teamplay
tag @a remove admin
tag @a remove tournament_admin
scoreboard players set @a adminMode 0
execute unless data storage xdu_race:config settings run function xdu_race:settings/capture
execute unless data storage xdu_race:config settings run data modify storage xdu_race:config settings set from storage xdu_race:scratch settings
