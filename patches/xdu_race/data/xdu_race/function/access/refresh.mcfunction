tag @a remove xdu_member
execute if data storage xdu_race:state current.roster[0] run function xdu_race:access/entry {index:0}
execute if data storage xdu_race:state current.roster[1] run function xdu_race:access/entry {index:1}
execute if data storage xdu_race:state current.roster[2] run function xdu_race:access/entry {index:2}
execute if data storage xdu_race:state current.roster[3] run function xdu_race:access/entry {index:3}
execute if data storage xdu_race:state current.roster[4] run function xdu_race:access/entry {index:4}
execute if data storage xdu_race:state current.roster[5] run function xdu_race:access/entry {index:5}
execute if data storage xdu_race:state current.roster[6] run function xdu_race:access/entry {index:6}
execute if data storage xdu_race:state current.roster[7] run function xdu_race:access/entry {index:7}
execute if data storage xdu_race:state current.roster[8] run function xdu_race:access/entry {index:8}
execute if data storage xdu_race:state current.roster[9] run function xdu_race:access/entry {index:9}
execute if data storage xdu_race:state current.roster[10] run function xdu_race:access/entry {index:10}
execute if data storage xdu_race:state current.roster[11] run function xdu_race:access/entry {index:11}
execute if data storage xdu_race:state current.roster[12] run function xdu_race:access/entry {index:12}
execute if data storage xdu_race:state current.roster[13] run function xdu_race:access/entry {index:13}
execute if data storage xdu_race:state current.roster[14] run function xdu_race:access/entry {index:14}
execute if data storage xdu_race:state current.roster[15] run function xdu_race:access/entry {index:15}
execute if data storage xdu_race:state current.roster[16] run function xdu_race:access/entry {index:16}
tag @a[tag=!xdu_member] add forcespectate
tag @a[tag=!xdu_member] remove playing
execute if data storage xdu_race:state current{state:"RUNNING"} run scoreboard players set @a[tag=xdu_member] afkTime 0
