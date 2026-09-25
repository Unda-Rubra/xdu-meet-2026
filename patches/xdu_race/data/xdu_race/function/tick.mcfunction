function xdu_race:access
execute if data storage xdu_race:state current{state:"RUNNING"} as @a[tag=xdu_member] run function xdu_race:observe
