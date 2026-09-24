scoreboard objectives add xdu dummy
scoreboard players add #boot xdu 1
scoreboard players set #native xdu 0
scoreboard players set #racepermit xdu 0
execute unless data storage xdu_race:state current run data modify storage xdu_race:state current set value {schema_version:1,adapter_version:"1.0.0",state:"IDLE",revision:0,boot_id:0,track_index:0,attempt_id:"none",roster:[],identity_mode:"offline_trusted_private",admin_policy:"host_only"}
execute if data storage xdu_race:state current{state:"ARMED"} run function xdu_race:error
execute if data storage xdu_race:state current{state:"RUNNING"} run function xdu_race:error
execute if data storage xdu_race:state current{state:"BETWEEN_TRACKS"} run function xdu_race:error
execute store result storage xdu_race:state current.boot_id int 1 run scoreboard players get #boot xdu
schedule function xdu_race:configure 3s replace
