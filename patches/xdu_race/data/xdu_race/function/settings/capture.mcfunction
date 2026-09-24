data modify storage xdu_race:scratch settings set value {}
execute store success storage xdu_race:scratch settings.BAIautocount int 1 if entity @s[tag=BAIautocount]
execute store success storage xdu_race:scratch settings.RAIautocount int 1 if entity @s[tag=RAIautocount]
execute store success storage xdu_race:scratch settings.absorpAlways int 1 if entity @s[tag=absorpAlways]
execute store success storage xdu_race:scratch settings.absorpNever int 1 if entity @s[tag=absorpNever]
execute store success storage xdu_race:scratch settings.allowAIfinish int 1 if entity @s[tag=allowAIfinish]
execute store success storage xdu_race:scratch settings.classicHUD int 1 if entity @s[tag=classicHUD]
execute store success storage xdu_race:scratch settings.endlessMode int 1 if entity @s[tag=endlessMode]
execute store success storage xdu_race:scratch settings.grandprixloop int 1 if entity @s[tag=grandprixloop]
execute store success storage xdu_race:scratch settings.noAIrival int 1 if entity @s[tag=noAIrival]
execute store success storage xdu_race:scratch settings.noCrowdSFX int 1 if entity @s[tag=noCrowdSFX]
execute store success storage xdu_race:scratch settings.noExtraChest int 1 if entity @s[tag=noExtraChest]
execute store success storage xdu_race:scratch settings.noMusicReset int 1 if entity @s[tag=noMusicReset]
execute store success storage xdu_race:scratch settings.noRubberBand int 1 if entity @s[tag=noRubberBand]
execute store success storage xdu_race:scratch settings.nospeedo int 1 if entity @s[tag=nospeedo]
execute store success storage xdu_race:scratch settings.optBAIalways int 1 if entity @s[tag=optBAIalways]
execute store success storage xdu_race:scratch settings.optBAInever int 1 if entity @s[tag=optBAInever]
execute store success storage xdu_race:scratch settings.optBAIsingle int 1 if entity @s[tag=optBAIsingle]
execute store success storage xdu_race:scratch settings.optBalance int 1 if entity @s[tag=optBalance]
execute store success storage xdu_race:scratch settings.optBattle int 1 if entity @s[tag=optBattle]
execute store success storage xdu_race:scratch settings.optChoose int 1 if entity @s[tag=optChoose]
execute store success storage xdu_race:scratch settings.optCustomRounds int 1 if entity @s[tag=optCustomRounds]
execute store success storage xdu_race:scratch settings.optInOrder int 1 if entity @s[tag=optInOrder]
execute store success storage xdu_race:scratch settings.optItems int 1 if entity @s[tag=optItems]
execute store success storage xdu_race:scratch settings.optItemsB int 1 if entity @s[tag=optItemsB]
execute store success storage xdu_race:scratch settings.optItemsR int 1 if entity @s[tag=optItemsR]
execute store success storage xdu_race:scratch settings.optMannequinAI int 1 if entity @s[tag=optMannequinAI]
execute store success storage xdu_race:scratch settings.optNoItems int 1 if entity @s[tag=optNoItems]
execute store success storage xdu_race:scratch settings.optNoLocatorBar int 1 if entity @s[tag=optNoLocatorBar]
execute store success storage xdu_race:scratch settings.optRAIalways int 1 if entity @s[tag=optRAIalways]
execute store success storage xdu_race:scratch settings.optRAInever int 1 if entity @s[tag=optRAInever]
execute store success storage xdu_race:scratch settings.optRAIsingle int 1 if entity @s[tag=optRAIsingle]
execute store success storage xdu_race:scratch settings.optRace int 1 if entity @s[tag=optRace]
execute store success storage xdu_race:scratch settings.optRandom int 1 if entity @s[tag=optRandom]
execute store success storage xdu_race:scratch settings.optRnB int 1 if entity @s[tag=optRnB]
execute store success storage xdu_race:scratch settings.optRoulette int 1 if entity @s[tag=optRoulette]
execute store success storage xdu_race:scratch settings.optVote int 1 if entity @s[tag=optVote]
execute store success storage xdu_race:scratch settings.randomPresetA int 1 if entity @s[tag=randomPresetA]
execute store success storage xdu_race:scratch settings.randomPresetB int 1 if entity @s[tag=randomPresetB]
execute store success storage xdu_race:scratch settings.teamplay int 1 if entity @s[tag=teamplay]
execute store success storage xdu_race:scratch settings.timeBalance int 1 if entity @s[tag=timeBalance]
execute store result storage xdu_race:scratch settings.allowInvis int 1 run scoreboard players get @s allowInvis
execute store result storage xdu_race:scratch settings.defLobbyTime int 1 run scoreboard players get @s defLobbyTime
execute store result storage xdu_race:scratch settings.difficultyRamp int 1 run scoreboard players get @s difficultyRamp
execute store result storage xdu_race:scratch settings.gamemodePresetA int 1 run scoreboard players get @s gamemodePresetA
execute store result storage xdu_race:scratch settings.gamemodePresetB int 1 run scoreboard players get @s gamemodePresetB
execute store result storage xdu_race:scratch settings.itemPresetA int 1 run scoreboard players get @s itemPresetA
execute store result storage xdu_race:scratch settings.itemPresetB int 1 run scoreboard players get @s itemPresetB
execute store result storage xdu_race:scratch settings.optAIdiff int 1 run scoreboard players get @s optAIdiff
execute store result storage xdu_race:scratch settings.optBAIcount int 1 run scoreboard players get @s optBAIcount
execute store result storage xdu_race:scratch settings.optBAIdiff int 1 run scoreboard players get @s optBAIdiff
execute store result storage xdu_race:scratch settings.optRAIcount int 1 run scoreboard players get @s optRAIcount
execute store result storage xdu_race:scratch settings.optRAIdiff int 1 run scoreboard players get @s optRAIdiff
execute store result storage xdu_race:scratch settings.customLapType int 1 run scoreboard players get @s customLapType
execute store result storage xdu_race:scratch settings.customLapMult int 1 run scoreboard players get @s customLapMult
execute store result storage xdu_race:scratch settings.customLapOffset int 1 run scoreboard players get @s customLapOffset
