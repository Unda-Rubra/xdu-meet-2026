scoreboard players set #request_ok xdu 0
execute unless data storage xdu_race:request operation_id run return 0
execute unless data storage xdu_race:request payload_hash run return 0
data modify storage xdu_race:scratch previous_operation set value ""
execute if data storage xdu_race:state current.operation_id run data modify storage xdu_race:scratch previous_operation set from storage xdu_race:state current.operation_id
execute store success score #new_operation xdu run data modify storage xdu_race:scratch previous_operation set from storage xdu_race:request operation_id
execute unless score #new_operation xdu matches 1 run return 0
execute store result score #expected xdu run data get storage xdu_race:request expected_revision
execute store result score #actual xdu run data get storage xdu_race:state current.revision
execute unless score #expected xdu = #actual xdu run return 0
execute store result score #expected_boot xdu run data get storage xdu_race:request expected_boot_id
execute store result score #actual_boot xdu run data get storage xdu_race:state current.boot_id
execute unless score #expected_boot xdu = #actual_boot xdu run return 0
scoreboard players set #request_ok xdu 1
