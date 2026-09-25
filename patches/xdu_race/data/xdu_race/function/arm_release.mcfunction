execute unless data storage xdu_race:state current{state:"WAITING"} run return 0
execute if data storage xdu_race:state current{release_armed:1b} run return 0
data modify storage xdu_race:state current.release_armed set value 1b
title @a actionbar {"text":"全部组已完成，本图结束；3秒后共同进入下一阶段。","color":"green"}
schedule function xdu_race:release_track 60t replace
