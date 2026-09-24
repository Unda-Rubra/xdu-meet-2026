scoreboard players set #instance_ok xdu 1
data modify storage xdu_race:scratch instance_expected set from storage xdu_race:config instance.template_hash
execute store success score #instance_changed xdu run data modify storage xdu_race:scratch instance_expected set from storage xdu_race:request plan.template_hash
execute if score #instance_changed xdu matches 1 run scoreboard players set #instance_ok xdu 0
data modify storage xdu_race:scratch instance_expected set from storage xdu_race:config instance.group
execute store success score #instance_changed xdu run data modify storage xdu_race:scratch instance_expected set from storage xdu_race:request plan.group
execute if score #instance_changed xdu matches 1 run scoreboard players set #instance_ok xdu 0
