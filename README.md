This is a minigame in development for the Kaylovespie Twitch chat. You can level up, collect piecoin loot, buy equipment, and hunt down other players. This game has permanent death, when you die you lose all levels and equipment and return to town. Subscribers trigger 4x experience bonus for a time.

To start your journey just type: !move fields

COMMANDS

!info - Show your level, eq, damage/defense, location, and specials/effects.
!move [location] - Moves to the location and starts leveling if there are monsters.
!buy [item] - Attempts to purchase and equip the desired weapon or armor.
!i - condensed version of info including experience progress.

!attack [player] - This will start an attack on a nearby player which will resolve in 20 seconds.
!defend - This will give you a defense bonus and prevent looting during an attack. Will not kill attacker.
!counter - This will attack your attacker giving you a small damage bonus.
!flee - This will give you a large defense bonus and but you may still be looted. You go to a random location. !move will also initiate a flee to the specified location.
!look [player] - Get an idea of your chances against a nearby player.

!dough - check piecoin balance.
!give [amount] [recipient] - give piecoins to a player. Giving to Piebank can remove bounty.
!bounty [amount] [target] - place piecoins on a player's head (loot reward).
!tax (amount) - This allows the king to tax everyone at a certain percentage (0-100).
!queen / !king - These commands adjust some messages for gender.
!vote [player] - Cast your vote for Pieland's hero. Must be level 5+ to vote.
!smite [player] - Put a peasant in their place. They must be less than level 5.
!unsmite [player] - Unban a player.
!stat - Show the current Hero and King/Queen of Pieland.
!song add [youtube] - Subs can add songs to the queue.

LOCATIONS

Town - This is where everyone starts. It is safe from monsters, and players get a defense bonus.
Castle - This is a safe haven from monsters and players, only honored guests allowed inside.
Fields - Mostly harmless and full of rabbits.
Forest - Spiders lurk here, beware.
River - Unknown
Swamps - Unknown
Mountains - Unknown
Ruins - Unknown
Desert - Unknown
Caves - Unknown
Crypt - Unknown
Abyss - Unknown
???? - Unknown

WEAPONS

( 5pc : lvl 1) Dagger
( 10pc: lvl 3) Wooden Club
( 25pc: lvl 6) Short Sword
( 50pc: lvl 9) Spear
( 100pc: lvl 12) Long Sword
( 250pc: lvl 15) Steel Axe
( 400pc: lvl 18) Katana
( 800pc: lvl 21) Spirit Lance
(2000pc: lvl 24) Enchanted Bow
(5000pc: lvl 27) Demon Edge

ARMOR

( 5pc : lvl 1) Cloth Robe
( 10pc: lvl 2) Fur Armor
( 25pc: lvl 4) Leather Armor
( 50pc: lvl 6) Copper Armor
( 100pc: lvl 8) Chainmail
( 250pc: lvl 10) Platemail
( 400pc: lvl 12) Silver Platemail
( 800pc: lvl 14) Assault Cuirass
(2000pc: lvl 16) Dragon Scalemail
(5000pc: lvl 18) Divine Aura

TRAITS

Every time you are born into Pieland at level 1 you will get a random trait:

Durable - Defense bonus in combat and less risk fighting lower levels
Strong - Damage bonus in combat and better chances fighting lower levels
Wise - Increased experience gain
Greedy - Extra loot from monsters, fleeing targets, and stealing.
Alert - No combat penalty when sneak attacked, will automatically flee if afk
Lucky - Less death chance when leveling and chance to recover from death
Violent - Less starting damage but gains damage for each kill
Pacifist - Gains armor every 2 levels but loses it for each kill

SPECIALS

These special powers are rare in Pieland. They will be granted every 15 levels or upon slaying Roshan. Most of them can be used on a nearby target player, or on the caster themselves if no one is specified. When obtaining a new special it is random, but you are guaranteed to get one you don't already have.

Specials are identified by a letter but casted with their full name (!guardian), cooldowns in seconds are displayed below.

(P)ersist - Holds onto specials and items upon death, but this special will disappear.
(S)tun (180) - Prevents specials, movement, and combat actions for 15 seconds.
(T)rack (300) - Shows the information of any target in Pieland. Dispels Invis.
(G)uardian (180) - Lowers death chance by 10% for 60 seconds. Can go to 0%. Works through repel. Prevents death from the fifth minute of Doom.
(E)mpower (120) - Damage boost for 60 seconds.
(R)epel (60) - Removes and prevents all special effects for 20 seconds. Works through stun.
(B)lind (90) - Greatly increases chance to miss for 20 seconds.
(C)urse (300) - Increase death chance by 5% for 1 hour.
(I)nvis (180) - Can't be targeted for 10 minutes (any pvp combat dispels this.)
Stea(L) (60) - Pickpockets a random amount up to 2% of a player's piecoins. 3% for greedy players. Dispels invis on self.

BOSSES

Roshan will spawn during special occasions and will grant a special to whomever lands the killing blow. Anyone who helps with the fight will gain experience. There is no level requirement to fight Roshan but anyone with low defense needs to be careful because he can kill you.

ADDITIONAL INFORMATION

Every minute you either gain experience or die depending on the area difficulty and your level/equipment. The weapon you have increases the experience you gain, and your armor reduces your death chance.

Pay attention to the difficulty hint when you move between areas. There is no hp but you will risk death every minute in harder areas. This can be a way to get ahead quickly if you are lucky though. You get reduced experience in areas with no chance of death. When you level you get some Piecoin loot based on how high the level. The highest level player may become the King of Pieland, and can tax monster loot for players level 5 and above only if they are outside of the castle. Only subscribers are allowed in the castle, but if you have killed someone in the last 2 minutes you will be denied entry (unless you are king).

Player vs player combat is only allowed for levels 5 and above, and is prohibited in the castle. Be aware that if you attack you are vulnerable to any number of players to sneak attack you in return without the ability to defend or flee. Once you are locked in combat you can only respond with one action and it cannot be changed during that round even if more players join combat. Only the player who lands the killing blow will earn tax free loot, and will gain extra loot from the victim kill count and any placed bounties. Experience may be gained by other participants. Kills show up on a player's info and will give more loot when they are killed themselves.

When the stream is offline you can't gain experience or die unless there is a live Roshan. Before you leave the channel or when the stream goes offline make sure to move to town (or castle) to be safe.


Possible additions:
ability to add gender, if gender is available, automatically adapt game to it (auto king/queen)

add make command, no automatic characters/revives, ability to choose name, cannot be same as prev character

notes

only 1 weapon at a time, possibility to second
only 1 armor at a time
each lvl has difficulty, if not high enough lvl, death chance goes up
towns - safe, 0% death chance
beginning terrains, 5-10% death chance
exp depending on difficulty, exponential exp gain with difficulty

battle system separate tick rate
after attack, certain amount of time to react, (20 seconds) to type a different command
success rate flee 45%
fight = 1 round
sneak attack, when attacking outside of village or town -> you cannot flee.
player vs multiple, find own system
there is a map, always the same
move has it's own cooldown, shorter CD then game tick.
exp gained depending on last time moved (safe time in db and filter on it)
cannot move while being attacked

boss fights
boss has HP, but players do not HP (1)
boss can take 25 hits
he attacks 1 player, but attacks hem twice
boss is in a zone, 1hour respawn time
boss only attacks after he is attacked, and then keeps doing so
zone is always there, but kind of safe zone, but no shopping
shopping only in towns
upon death: lose everything except coins
Persist ability: get best weapon for lvl until you reach your persisted weapon

default currency


idea for new minigame: the family game werewolfs
every person gets hes role whispered, bot or streamer is game leader
can be fun interactive
https://steamcommunity.com/groups/kaylovespie/discussions/0/598198356166839850/