execute unless data storage xdu_race:state current{state:"WAITING"} run return 0
data remove storage xdu_race:state current.release_armed
gamemode adventure @a[tag=xdu_member,tag=!xdu_admin]
tag @a[tag=xdu_member,tag=!xdu_admin] remove forcespectate
data modify storage xdu_race:state current.state set value "RUNNING"
execute as @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function sprint_racer:game_logic/0/_initialize
function xdu_race:access
function xdu_race:bump
