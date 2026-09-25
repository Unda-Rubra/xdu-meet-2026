scoreboard objectives add xdu dummy
execute unless data storage xdu_race:state current run data modify storage xdu_race:state current set value {adapter_version:"2.0.0",state:"IDLE",revision:0,boot_id:0,attempt_id:"none",roster:[]}
execute if data storage xdu_race:state current{state:"RUNNING"} run data modify storage xdu_race:state current.state set value "ERROR"
scoreboard players add #boot xdu 1
execute store result storage xdu_race:state current.boot_id int 1 run scoreboard players get #boot xdu
scoreboard players set #start xdu 0
