$data modify storage xdu_race:scratch slot set from storage xdu_race:state current.tracks[$(index)]
$data modify storage xdu_race:scratch slot.slot set value $(slot)
$data modify storage xdu_race:scratch slot.z set value $(z)
function xdu_race:validate_slot_inner with storage xdu_race:scratch slot
