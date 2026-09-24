$execute as @a[name=$(name),nbt={UUID:$(uuid_int)}] run tag @s add xdu_member
$execute as @a[name=$(name),nbt={UUID:$(uuid_int)}] run scoreboard players set @s xdu $(index)
