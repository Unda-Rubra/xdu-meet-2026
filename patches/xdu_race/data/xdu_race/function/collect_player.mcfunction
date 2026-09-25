$data modify storage xdu_race:state current.results."$(uuid)" set value {status:"DISCONNECTED"}
$execute store result storage xdu_race:state current.results."$(uuid)".total int 1 run scoreboard players get $(name) gpPoints
$execute if entity @a[name=$(name),tag=xdu_member,tag=!xdu_admin] run data modify storage xdu_race:state current.results."$(uuid)".status set value "FINISHED"
