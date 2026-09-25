function xdu_race:capture_cell with storage xdu_race:scratch cursor
scoreboard players add #captureX xdu 1
execute if score #captureX xdu matches 1590 run scoreboard players add #captureZ xdu 1
execute if score #captureX xdu matches 1590 run scoreboard players set #captureX xdu 1584
execute store result storage xdu_race:scratch cursor.x int 1 run scoreboard players get #captureX xdu
execute store result storage xdu_race:scratch cursor.z int 1 run scoreboard players get #captureZ xdu
execute if score #captureZ xdu matches ..422 run function xdu_race:capture_grid
