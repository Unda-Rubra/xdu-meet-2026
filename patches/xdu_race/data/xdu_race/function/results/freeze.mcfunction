execute unless data storage xdu_race:state current.tracks[{index:0,settled:1b}] run return 0
execute unless data storage xdu_race:state current.tracks[{index:1,settled:1b}] run return 0
execute unless data storage xdu_race:state current.tracks[{index:2,settled:1b}] run return 0
execute unless data storage xdu_race:state current.tracks[{index:3,settled:1b}] run return 0
execute unless data storage xdu_race:state current.tracks[{index:4,settled:1b}] run return 0
execute unless data storage xdu_race:state current.tracks[{index:5,settled:1b}] run return 0
data modify storage xdu_race:state current.state set value "GP_FINISHED"
data modify storage xdu_race:state current.frozen set value 1b
data modify storage xdu_race:state current.pending_adjudication set value 1b
scoreboard players set #gate xdu 0
