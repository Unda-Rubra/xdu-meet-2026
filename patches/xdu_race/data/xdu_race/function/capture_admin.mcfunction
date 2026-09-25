data modify storage xdu_race:scratch admin set value {}
data modify storage xdu_race:scratch admin.uuid set from entity @s UUID
data modify storage xdu_race:scratch admin.tags set from entity @s Tags
data modify storage xdu_race:scratch admins append from storage xdu_race:scratch admin
