execute unless entity @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1] run return run schedule function xdu_lobby:initialize 1s replace
execute as @e[type=armor_stand,tag=w,x=1560,y=150,z=406,distance=..1] run function sprint_racer:game_logic/0/_initialize
setworldspawn 1556 89 406
data modify storage xdu_lobby:state ready set value 1b
