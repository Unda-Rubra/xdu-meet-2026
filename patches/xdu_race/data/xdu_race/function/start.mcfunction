execute unless data storage xdu_race:state current{state:"PREPARED"} run return 0
data modify storage xdu_race:state current.state set value "RUNNING"
scoreboard players set #start xdu 1
execute as @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/11/start_grand_prix
scoreboard players set #start xdu 0
function xdu_race:access
function xdu_race:bump
