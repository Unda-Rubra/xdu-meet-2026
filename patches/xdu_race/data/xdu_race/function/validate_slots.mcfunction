function xdu_race:validate_slot {slot:1,index:0,z:373}
function xdu_race:validate_slot {slot:2,index:1,z:374}
function xdu_race:validate_slot {slot:3,index:2,z:375}
function xdu_race:validate_slot {slot:4,index:3,z:376}
function xdu_race:validate_slot {slot:5,index:4,z:377}
function xdu_race:validate_slot {slot:6,index:5,z:378}
execute unless score @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] gpNumber matches 6 run scoreboard players set #valid xdu 0
