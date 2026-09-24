$execute store result score #matches xdu if entity @e[type=armor_stand,tag=gpNo$(slot)]
execute unless score #matches xdu matches 1 run scoreboard players set #valid xdu 0
$execute unless entity @e[type=armor_stand,tag=gpNo$(slot),tag=trackStandR,tag=!rtBlacklist,scores={rNumber=$(native_id)}] run scoreboard players set #valid xdu 0
$execute unless block 1584 39 $(z) minecraft:light_blue_wool run scoreboard players set #valid xdu 0
$execute unless block 1585 39 $(z) minecraft:stone run scoreboard players set #valid xdu 0
$execute unless block 1586 39 $(z) minecraft:oak_planks run scoreboard players set #valid xdu 0
$execute unless block 1587 39 $(z) minecraft:stone run scoreboard players set #valid xdu 0
$execute unless block 1588 39 $(z) minecraft:stone run scoreboard players set #valid xdu 0
$execute unless block 1589 39 $(z) minecraft:stone run scoreboard players set #valid xdu 0
