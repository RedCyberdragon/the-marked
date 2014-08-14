########################################################################################################
# themarked.py
#    by Stephen Gatten
# Main Python script file for Forcastia Tales: The Marked, a roguelike made to follow the Complete
# Roguelike Tutorial Using Python and LibTCOD, available on RogueBasin.
# http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python%2Blibtcod
# http://www.forcastia.com
#    Last updated on July 10, 2014
########################################################################################################

import libtcodpy as libtcod
import math
import textwrap
import shelve

#Screen Size
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

#Status Panel
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MESSAGE_X = BAR_WIDTH + 2
MESSAGE_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MESSAGE_HEIGHT = PANEL_HEIGHT - 1

INVENTORY_WIDTH = 50
ADVANCE_MENU_WIDTH = 40
MIRROR_SCREEN_WIDTH = 30

HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#Experience and Leveling
#A player levels up upon attaining ADVANCE_BASE + (level * ADVANCE_FACTOR) experience
ADVANCE_BASE = 200
ADVANCE_FACTOR = 150

#Map Size
MAP_WIDTH = 80
MAP_HEIGHT = 43

#Parameters for the Dungeon Generator
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
#MAX_ROOM_MONSTERS = 3
#MAX_ROOM_ITEMS = 2

#Field of View Constants
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

#FPS Limit
FPS_LIMIT = 20

#Common Glyphs
gMarked = "@"
gSpace = " "
gFloor = "."
gFood = "%"
gPotion = "?"
gScroll = "!"

#Common Colors
#cDarkWall = libtcod.Color(0,0,100)
#cDarkGround = libtcod.Color(50,50,150)
cDarkWall = libtcod.darkest_blue
cDarkGround = libtcod.darker_blue
cLitWall = libtcod.Color(130, 110, 50)
cLitGround = libtcod.Color(200, 180, 50)

#The Object class describes a generic game object, such as the player, a monster, an item, or a
#dungeon feature. All objects have an ASCII character, or "glyph" which represents the object on
#the game screen.	
class Object:
	#INIT initializes and constructs the object with the given parameters.
	def __init__(self, x, y, glyph, name, color, blocks = False, alwaysVisible = False, 
		fighter = None, ai = None, item = None, equipment = None):
		self.name = name
		self.blocks = blocks
		self.x = x
		self.y = y
		self.glyph = glyph
		self.color = color
		self.alwaysVisible = alwaysVisible
		
		self.fighter = fighter
		if self.fighter:
			self.fighter.owner = self
		
		self.ai = ai
		if self.ai:
			self.ai.owner = self
			
		self.item = item
		if self.item:
			self.item.owner = self
			
		self.equipment = equipment
		if self.equipment:
			self.equipment.owner = self
			self.item = Item()
			self.item.owner = self
	
	#MOVE moves the character by the given amount in directionX and directionY.
	def move(self, directionX, directionY):
		if not isBlocked(self.x + directionX, self.y + directionY):
			self.x += directionX
			self.y += directionY
	
	#DRAW sets the color and draws the object's glyph at its position.
	def draw(self):
		if (libtcod.map_is_in_fov(fovMap, self.x, self.y) or (self.alwaysVisible and map[self.x][self.y].explored)):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.glyph, libtcod.BKGND_NONE)
		
	#CLEAR erases this object's glyph.
	def clear(self):
		libtcod.console_put_char(con, self.x, self.y, gSpace, libtcod.BKGND_NONE)
		
	#MOVE TOWARDS gets a vector and distance from the object to the target, so the object can
	#move toward the target, as in a pursuit.
	def moveTowards(self, targetX, targetY):
		directionX = targetX - self.x
		directionY = targetY - self.y
		distance = math.sqrt(directionX ** 2 + directionY ** 2)
		
		#Normalize the vector to a length of 1, preserving direction, then round it and convert to
		#an integer so the movement is restricted to the map grid.
		directionX = int(round(directionX / distance))
		directionY = int(round(directionY / distance))
		self.move(directionX, directionY)
		
	#DISTANCE TO returns the distance from this object to another object.
	def distanceTo(self, other):
		directionX = other.x - self.x
		directionY = other.y - self.y
		return math.sqrt(directionX ** 2 + directionY ** 2)
		
	#SEND TO BACK makes it so that this object is drawn first, and all other objects on the same tile
	#appear above this object.
	def sendToBack(self):
		global objects
		
		objects.remove(self)
		objects.insert(0,self)
		
	#DISTANCE returns the distance between this object and a tile.
	def distance(self, x, y):
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

#Not all objects in the game, such as the player, monsters, NPCs, etc. will use the exact same properties.
#Older roguelikes used a data-driven approach, having all objects have the exact same set of properties.
#and only the values of these properties are modified from object to object. There isn't feature variation
#between different objects. However, this solution can be tedious if we need to implement a new property
#for all objects when it only applies to one or two. The only workaround to this puzzle is to limit the
#number of properties.
#A popular alternative is inheritance, where a hierarchy of parent and child classes is designed. This
#reduces redundancy, but properties of parents and children can conflict if they share names. There is
#also the temptation to define deep hierarchies of classes, such as Object - Item - Equipment - Weapon -
#Melee Weapon - Blunt Weapon - Mace. Each level can add just a tiny bit of functionality over the last,
#and in this system, for example, a Mace could not be both a Weapon and a Magic Item.
#The solution we will use in this particular program is called composition. There's the object class,
#and some component classes. A component class defines extra properties and methods for an Object that
#needs them. You can instantiate an instance of the component class as a property of the Object, at
#which point it "owns" the component.

#The Fighter class describes an Object that is capable of entering into combat. Any object that can
#fight or be attacked must have this component.
class Fighter:
	#INIT initializes and constructs the fighter component.
	def __init__(self, hp, atk, dfn, xp, deathEffect = None):
		self.hits = hp
		self.cond = hp
		self.atk = atk
		self.dfn = dfn
		self.xp = xp
		self.deathEffect = deathEffect
		
	#TAKE DAMAGE handles damage and hit point loss.
	def takeDamage(self, damage):
		if damage > 0:
			self.cond -= damage
			
			#Check for death. If there is a death function and the fighter's health is zero or lower,
			#call the death function.
			if self.cond <= 0:
				function = self.deathEffect
				if function is not None:
					function(self.owner)
					
				#Yield experience to the player.
				if self.owner != player:
					player.fighter.xp += self.xp
					message("You gain " + str(self.xp) + " spirit points.", libtcod.orange)
			
	#ATTACK handles a fighter's attack against another fighter.
	def attack(self, target):
		damage = self.atk - target.fighter.dfn
		
		if damage > 0:
			if (target.fighter.cond - damage) <= 0:
				message(self.owner.name.capitalize() + " attacks " + target.name + " for " + str(damage)
					+ " points of damage, killing it!")
			else:
				message(self.owner.name.capitalize() + " attacks " + target.name + " for " + str(damage)
					+ " points of damage.")
			target.fighter.takeDamage(damage)
		else:
			message(self.owner.name.capitalize() + " attacks " + target.name + " but it has no effect!")
		
	#HEAL increases a fighter's current hitpoints, but cannot go over the maximum.
	def heal(self, amount):
		self.cond += amount
		if self.cond > self.hits:
			self.cond = self.hits
	
#This BasicMonster class contains AI routines for a standard monster.	
class BasicMonster:
	#TAKE TURN processes a standard monster's turn. If you can see it, it can see you, and it will
	#move toward you.
	def takeTurn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fovMap, monster.x, monster.y):
			#If the monster is far away, it moves toward the player.
			if monster.distanceTo(player) >= 2:
				monster.moveTowards(player.x, player.y)
				
			#if the monster is close enough, and the player is alive, the monster attacks.
			elif player.fighter.cond > 0:
				monster.fighter.attack(player)

#The ConfusedMonster AI module is used for a monster afflicted with confusion.
class ConfusedMonster:
	def __init__(self, oldAI, numberOfTurns = CONFUSE_NUM_TURNS):
		self.oldAI = oldAI
		self.numberOfTurns = numberOfTurns
		
	#TAKE TURN processes a confused monster's turn. If the confusion has not worn off, the monster wanders
	#randomly and does not attack.
	def takeTurn(self):
		if self.numberOfTurns > 0:
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.numberOfTurns -= 1
			
		else:
			#When confusion wears off, the previous AI will be restored, and the confused
			#AI will be deleted due to not being referenced anymore.
			self.owner.ai = self.oldAI
			message("The " + self.owner.name + " is no longer confused.", libtcod.red)
		
#The Item class describes an object that can be picked up and used by the player.				
class Item:
	#INIT constructs the item component.
	def __init__(self, useEffect = None):
		self.useEffect = useEffect
	
	#PICKUP removes the item from the map and adds the item to the player's inventory.
	def pickup(self):
		if len(inventory) >= 26:
			message("Your inventory is full.", libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message("Picked up a " + self.owner.name + ".", libtcod.green)
			
			#If an item is a piece of equipment, and the slot is free, equip it
			equipment = self.owner.equipment
			if equipment and getEquippedInSlot(equipment.slot) is None:
				equipment.equip()
	
	#USE evokes the item's use function. If the item is a piece of Equipment, then its use is to
	#toggle the equipment status.
	def use(self):
		if self.owner.equipment:
			self.owner.equipment.toggleEquip()
			return
		
		if self.useEffect is None:
			message("You cannot use the " + self.owner.name + " now.")
		else:
			if self.useEffect() != "cancel":
				#Destroy the item after use, unless it was cancelled.
				inventory.remove(self.owner) 
	
	#DROP removes the item from the player's inventory and adds it to the map objects.
	def drop(self):
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message("You dropped a " + self.owner.name + ".", libtcod.yellow)
		
		if self.owner.equipment:
			self.owner.equipment.unequip()

#The Equipment class describes an object that can be equipped by the player, yielding bonuses.
class Equipment:
	#INIT constructs the equipment component.
	def __init__(self, slot):
		self.slot = slot
		self.isWorn = False
		
	#TOGGLE EQUIP toggles the isEquipped status. An unequipped item will become equipped, and vice versa.
	def toggleEquip(self):
		if self.isWorn:
			self.unequip()
		else:
			self.equip()
			
	#EQUIP wields or wears the item, showing a message about it, and yields the bonus.
	def equip(self):
		#If the slot is already being used, unequip whatever is there first.
		oldEquipment = getEquippedInSlot(self.slot)
		if oldEquipment is not None:
			oldEquipment.unequip()
			
		self.isWorn = True
		message("You have equipped the " + self.owner.name, libtcod.light_green)
		
	#UNEQUIP takes the item off, showing a message about it, and rescinds the bonus.
	def unequip(self):
		if not self.isWorn:
			message("That item is not currently equipped.", libtcod.light_green)
			return
		self.isWorn = False
		message("You have unequipped the " + self.owner.name, libtcod.light_green)
		
#The Tile class describes a given tile on the map and its properties.
class Tile:
	#INIT initializes and constructs the tile with the given parameters.
	def __init__(self, blocked, blockSight = None):
		self.blocked = blocked
		self.explored = False
		
		#By default, if a tile is blocked, it will also block line of sight.
		if blockSight is None: blockSight = blocked
		self.blockSight = blockSight

#The Rectangle class defines a rectangle of tiles on the map, and is used to characterize a room.
class Rectangle:
	#INIT constructs a rectangle by taking the top-left coordinates in tiles and its size, to define
	#it in terms of two points - the top-left (x1,y1) and the bottom-right (x2,y2).
	def __init__(self, x, y, width, height):
		self.x1 = x
		self.y1 = y
		self.x2 = x + width
		self.y2 = y + height
		
	#CENTER returns the center coordinates of the rectangle.
	def center(self):
		centerX = (self.x1 + self.x2) / 2
		centerY = (self.y1 + self.y2) / 2
		return (centerX, centerY)
	
	#INTERSECT returns true if this rectangle intersects with another one.
	def intersect(self, other):
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
			self.y1 <= other.y2 and self.y2 >= other.y1)

def carveRoom(room):
	global map
	
	#Go through the tiles in the rectangle and make them passable. Incrementing x1 and y1 by 1
	#ensures that there is always a one-tile wall around a room.
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].blockSight = False

#This function carves a horizontal tunnel of unblocked tiles.
def carveHorizontalTunnel(x1, x2, y):
	global map
	
	#MIN and MAX return the minimum and maximum of two given values, respectively. For loops only work
	#from a lower value to a higher value. Min and max ensure that, no matter which is lower, x1 or x2,
	#the for loop will work as intended.
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].blockSight = False
			
#This function carves a vertical tunnel of floor tiles.
def carveVerticalTunnel(y1, y2, x):
	global map
	
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].blockSight = False

#This function checks to see if a tile is blocked.
def isBlocked(x, y):
	#First, test the tile itself.
	if map[x][y].blocked:
		return True
	
	#Now, check for any blocking objects.
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
	
	return False

#This function places objects into a room.
def placeObjects(room):
	#Maximum number of monsters per room.
	maxMonsters = fromDungeonLevel([[2,1], [3, 4], [5,6]])
	
	monsterChances = {}
	monsterChances["orc"] = 80
	monsterChances["troll"] = fromDungeonLevel([[15, 3], [30, 5], [60, 7]])
	
	#Maximum number of items per room.
	maxItems = fromDungeonLevel([[1,1], [2,4]])
	
	itemChances = {}
	itemChances["heal"] = 35
	itemChances["lightning"] = fromDungeonLevel([[25,4]])
	itemChances["fireball"] = fromDungeonLevel([[25,6]])
	itemChances["confuse"] = fromDungeonLevel([[10,2]])
	
	#Choose a random number of monsters below the maximum
	numberOfMonsters = libtcod.random_get_int(0, 0, maxMonsters)
	#monsterChances = {"orc": 80, "troll": 20}
	#itemChances = {"heal": 70, "lightning": 10, "fireball": 10, "confuse": 10}
	#itemChances["sword"] = 25
	
	for i in range(numberOfMonsters):
		#Choose a random spot for this monster. X and Y values are offset by one because the room's
		#rectangle includes its walls as well, and if it picks a wall tile, it will not get created
		#due to the tile being blocked.
		x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
		y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
		
		if not isBlocked(x,y):
			#Only place the object if the tile is not blocked.
			choice = chooseFromDict(monsterChances)
			if choice == "orc":
				fighterComponent = Fighter(20, 4, 0, 35, monsterDeath)
				aiComponent = BasicMonster()
				
				monster = Object(x, y, "o", "Orc", libtcod.desaturated_green,
					blocks = True, fighter = fighterComponent, ai = aiComponent)
			else:
				fighterComponent = Fighter(30, 8, 2, 100, monsterDeath)
				aiComponent = BasicMonster()
				
				monster = Object(x, y, "T", "Troll", libtcod.darker_green,
					blocks = True, fighter = fighterComponent, ai = aiComponent)
					
			objects.append(monster)
	
	numberOfItems = libtcod.random_get_int(0, 0, maxItems)
	
	for i in range(numberOfItems):
		#Choose a random spot for this item.
		x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
		y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

		if not isBlocked(x,y):
			#Only place this item if the tile is not blocked.
			choice = chooseFromDict(itemChances)
			if choice == "heal":
				itemComponent = Item(useEffect = castHeal)
				item = Object(x, y, gPotion, "Healing Potion", libtcod.violet, item = itemComponent)
			elif choice == "lightning":
				itemComponent = Item(useEffect = castLightning)
				item = Object(x, y, gScroll, "Scroll of Lightning Bolt", libtcod.light_yellow, item = itemComponent)
			elif choice == "fireball":
				itemComponent = Item(useEffect = castFireball)
				item = Object(x, y, gScroll, "Scroll of Fireball", libtcod.light_yellow, item = itemComponent)
			#elif choice == "sword":
			#	equipmentComponent = Equipment(slot = "weapon")
			#	item = Object(x, y, "/", "Sword", libtcod.sky, equipment = equipmentComponent)
			else:
				itemComponent = Item(useEffect = castConfuse)
				item = Object(x, y, gScroll, "Scroll of Confuse", libtcod.light_yellow, item = itemComponent) 
			
			item.alwaysVisible = True
			objects.append(item)
			item.sendToBack() #Items appear below other objects.
		
def makeMap():
	global map, objects, stairsDown
	
	#First, instantiate the list of objects, with just the player at this point.
	objects = [player]
	
	#Fill the map with "blocked" tiles. This uses a construct called a list comprehension. When
	#making a list comprehension such as this, it is imperative to always call the constructor of
	#the objects that are being created. For example, if we attempted to first create a variable,
	#and then refer to that variable here, all elements in this list would point to that same variable.
	#Calling the constructor ensures that all of these Tiles are distinct instances.
	map = [[ Tile(True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
	
	rooms = []
	numberOfRooms = 0
	
	for r in range(MAX_ROOMS):
		#Random width and height.
		width = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		height = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		
		#Random position, without going out of the boundaries of the map
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - width - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - height - 1)
		
		newRoom = Rectangle(x, y, width, height)
		
		#Run through the other rooms to see if they intersect with this one. If it intersects with any
		#other rooms, reject the room and break from the loop.
		failed = False
		for otherRoom in rooms:
			if newRoom.intersect(otherRoom):
				failed = True
				break
		
		if not failed:
			#This point in the loop means that there are no intersections, so this room is valid. We
			#now paint it to the map's tiles.
			carveRoom(newRoom)
			placeObjects(newRoom)
			
			#Gather center coordinates of new room.
			(newX, newY) = newRoom.center()
			
			#Optionally, print a "room number" glyph to see how the map drawing worked. We may have more
			#than ten rooms, so we will print A for the first room, B for the next, etc. If this exceeds
			#the given uppercase letters, it will begin labelling rooms with various symbols and then
			#lowercase letters. However, this will not explicitly fail unless we exceed sixty-two rooms.
			#roomNumber = Object(newX, newY, chr(65 + numberOfRooms), "Room Number", libtcod.white, False)
			#objects.insert(0, roomNumber)
			
			if numberOfRooms == 0:
				#This must be the first room, so the player will start here.
				player.x = newX
				player.y = newY
			else:
				#For all rooms after the first, we must connect it to the previous room using a tunnel.
				#Not every room can be connected using a strictly horizontal or vertical tunnel. For
				#example, if a room is in the top left, and the second room is in the bottom right, both
				#horizontal tunnel and a vertical tunnel will be needed. Either tunnel can be carved
				#first, so we will choose between these two possibilities randomly.
				
				#Gather center coordinates of previous room.
				(prevX, prevY) = rooms[numberOfRooms - 1].center()
				
				if libtcod.random_get_int(0, 0, 1) == 1:
					#First move horizontally, then vertically.
					carveHorizontalTunnel(prevX, newX, prevY)
					carveVerticalTunnel(prevY, newY, newX)
				else:
					#First move vertically, then horizontally.
					carveVerticalTunnel(prevY, newY, prevX)
					carveHorizontalTunnel(prevX, newX, newY)
			
			#Finally, append the new room to the list.
			rooms.append(newRoom)
			numberOfRooms += 1
		
	#Create stairs down at the center of the last room.
	stairsDown = Object(newX, newY, ">", "Stairs Down", libtcod.white, alwaysVisible = True)
	objects.append(stairsDown)
	stairsDown.sendToBack()

#This function controls the player's movement and attack actions.
def playerMoveOrAttack(directionX, directionY):
	global fovNeedsToBeRecomputed
	
	#The coordinates the player is moving to, or attacking toward
	x = player.x + directionX
	y = player.y + directionY
	
	#Try to find an attackable object there
	target = None
	for object in objects: 
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
	
	#Attack if a target is found, move otherwise.
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(directionX, directionY)
		fovNeedsToBeRecomputed = True
			
def handleKeys():
	global fovNeedsToBeRecomputed, keys
	
	keyChar = chr(key.c)
	
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt-Enter toggles fullscreen.
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	elif key.vk == libtcod.KEY_ESCAPE:
		#Escape exits the game.
		return "exit"
	
	if gameState == "playing":
		#movement keys
		#if libtcod.console_is_key_pressed(libtcod.KEY_UP):
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			playerMoveOrAttack(0,-1) #North
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			playerMoveOrAttack(0,1) #South
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			playerMoveOrAttack(-1,0) #West
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			playerMoveOrAttack(1,0)	#East
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			playerMoveOrAttack(-1, -1) #Northwest
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			playerMoveOrAttack(1, -1) #Northeast
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			playerMoveOrAttack(-1, 1) #Southwest
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			playerMoveOrAttack(1, 1) #Southeast
		elif keyChar == "." or key.vk == libtcod.KEY_KP5:
			pass  #Do nothing this turn.
		else:
			#Test for other keys.
			if keyChar == "g":
				#(G)et picks up an item.
				for object in objects:
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pickup()
						break
			if keyChar == "i":
				#(I)nventory brings up the player's inventory.
				chosenItem = inventoryMenu("Press the key next to an item name to use it, or any other key to cancel.\n")
				if chosenItem is not None:
					chosenItem.use()
			if keyChar == "d":
				#(D)rop drops an item to the ground.
				chosenItem = inventoryMenu("Press the key next to an item to drop it, or any other to cancel.\n")
				if chosenItem is not None:
					chosenItem.drop()
			if keyChar == "c":
				#(C)haracter shows character information.
				xpToAdvance = ADVANCE_BASE + player.level * ADVANCE_FACTOR
				announce("You gaze into your mirror and reflect...\n"
					+ "\nCourage Level:     " + str(player.level)
					+ "\nSpirit:            " + str(player.fighter.xp)
					+ "\nSpirit To Advance: " + str(xpToAdvance)
					+ "\nHealth:            " + str(player.fighter.hits)
					+ "\nAttack:            " + str(player.fighter.atk)
					+ "\nDefense:           " + str(player.fighter.dfn), MIRROR_SCREEN_WIDTH)
			if keyChar == ">":
				#Descend stairs, if the player is on them.
				if stairsDown.x == player.x and stairsDown.y == player.y:
					nextLevel()
			
			return "no turn taken"

def getNamesUnderMouse():
	global mouse
	
	#Return a string with the names of all objects under the mouse cursor.
	(x, y) = (mouse.cx, mouse.cy)
	
	#Create a list with the names of all the objects at the mouse's coordinates. These objects must
	#be within the player's FOV, however, or else they would be able to detect things through walls.
	#This uses the if variant of a list comprehension.
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fovMap, obj.x, obj.y)]
	
	#Join the names, separated by commas, and return the list with the first letter capitalized.
	names = ", ".join(names)
	return names.capitalize()
	
#This function displays messages in the message log on the status bar.
def message(newMessage, color = libtcod.white):
	#Split the message if necessary, among multiple lines. This uses Python's textwrap module.
	newMessageLines = textwrap.wrap(newMessage, MESSAGE_WIDTH)
	
	for line in newMessageLines:
		#If the buffer is full, remove the first line to make room for the new one.
		if len(messageLog) == MESSAGE_HEIGHT:
			del messageLog[0]
		
		#Add the new line as a tuple, with the text and the color.
		messageLog.append( (line, color) )

#This function renders a generic status bar, used for a health bar, a mana bar, experience bar, etc.
def renderStatusBar(x, y, totalWidth, name, value, maximum, barColor, backColor):
	#First, calculate width of the bar.
	barWidth = int(float(value) / maximum * totalWidth)
	
	#Render the background first.
	libtcod.console_set_default_background(panel, backColor)
	libtcod.console_rect(panel, x, y, totalWidth, 1, False, libtcod.BKGND_SCREEN)
	
	#Now render the bar on top.
	libtcod.console_set_default_background(panel, barColor)
	if barWidth > 0:
		libtcod.console_rect(panel, x, y, barWidth, 1, False, libtcod.BKGND_SCREEN)
	
	#Finally, some centered text with the values.
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + totalWidth / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, 
		name + ": " + str(value) + "/" + str(maximum))
		
#This function draws the map and all objects.
def renderAll():
	global fovNeedsToBeRecomputed

	if fovNeedsToBeRecomputed:
		#If this is true, then we must recalculate the field of view and render the map.
		fovNeedsToBeRecomputed = False
		libtcod.map_compute_fov(fovMap, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		
		#Iterate through the list of map tiles and set their background colors.
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fovMap, x, y)
				wall = map[x][y].blockSight
				if not visible:
					#If a tile is out of the player's field of view...
					if map[x][y].explored:
						#...it will only be drawn if the player has explored it
						if wall:
							libtcod.console_set_char_background(con, x, y, cDarkWall, libtcod.BKGND_SET)
						else:
							libtcod.console_set_char_background(con, x, y, cDarkGround, libtcod.BKGND_SET)
				else:
					#If a tile is in the player's field of view...
					if wall:
						libtcod.console_set_char_background(con, x, y, cLitWall, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, x, y, cLitGround, libtcod.BKGND_SET)
					map[x][y].explored = True
	
	#Draw all objects in the list, except the player, which needs to be drawn last.
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
		
	#Blit the contents of con to the root console.
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
	
	#Prepare to render the status panel.
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	
	#Print the message log, one line at a time.
	y = 1
	for (line, color) in messageLog:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MESSAGE_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
	
	#Show the player's stats
	renderStatusBar(1, 1, BAR_WIDTH, "Health", player.fighter.cond, player.fighter.hits, libtcod.red, libtcod.darkest_red)
	
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, "Dungeon Level: " + str(dungeonLevel))
	
	#Display the names of objects under the mouse cursor.
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, getNamesUnderMouse())
	
	#Blit the contents of panel to the root console.
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
		
def playerDeath(player):
	#Upon the player's death, the game ends.
	global gameState
	message("You have died!", libtcod.red)
	gameState = "dead"
	
	#For added effect, transform the player into a corpse
	player.glyph = gFood
	player.color = libtcod.dark_red

def monsterDeath(monster):
	#Upon a monster's death, it becomes a corpse, can't be attacked, and does not move
	#message(monster.name.capitalize() + " is dead!", libtcod.orange)
	monster.glyph = gFood
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = "Remains of " + monster.name
	monster.sendToBack()
	
#This function displays a window with a string (header) at the top, and a list of strings (options).
#The height of the menu is implicit as it depends on the header height and number of options, but the
#width is defined in the method. A letter will be shown next to each option (A, B, etc) so the user can
#select it by pressing that key. The function returns the index of the selected option, starting with
#zero, or None if the user pressed a different key.
def menu(header, options, width):
	if len(options) > 26: raise ValueError("Cannot have a menu with more than twenty-six options.")
	
	#Calculate total height for the header (after auto-wrap) and one line per option.
	headerHeight = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == "":
		headerHeight = 0
	height = len(options) + headerHeight
	
	#Create an off-screen console that represents the menu's window.
	window = libtcod.console_new(width, height)
	
	#Print the header, with auto-wrap.
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	
	#Print all the options, one by one. ORD and CHR are built-in Python functions. chr(i) returns a string
	#of one character whose ASCII code is in the integer i - for example, chr(97) returns "a". ord(c) is
	#the opposite - given a string of length one, it returns an integer representing the Unicode code
	#point of the character - for example, ord("a") returns 97.
	y = headerHeight
	letterIndex = ord("a")
	for optionText in options:
		text = "(" + chr(letterIndex) + ") " + optionText
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letterIndex += 1
		
	#Blit the contents of window to the root console. The last two parameters passed to console_blit
	#define the foreground and background transparency, respectively.
	x = SCREEN_WIDTH / 2 - width / 2
	y = SCREEN_HEIGHT / 2 - height / 2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
	
	#Present the root console to the player and wait for a keypress.
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt-Enter toggles fullscreen.
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	
	#Convert the ASCII code to an index. If it corresponds to an option, return it, otherwise return None
	index = key.c - ord("a")
	if index >= 0 and index < len(options): 
		return index
	
	return None
	
#This function shows a menu with each item of the player's inventory as an option.
def inventoryMenu(header):
	if len(inventory) == 0:
		options = ["Inventory is empty."]
	else:
		options = []
		for item in inventory:
			text = item.name
			#Show additional information, in case it's equipped.
			if item.equipment and item.equipment.isWorn:
				text = text + "(Equipped)"
			options.append(text)
		
	index = menu(header, options, INVENTORY_WIDTH)
	
	#If an item was chosen, return it.
	if index is None or len(inventory) == 0: 
		return None
	return inventory[index].item
	
#This function heals the player.
def castHeal():
	if player.fighter.cond == player.fighter.hits:
		message("You are already at full health.", libtcod.red)
		return "cancel"
	
	message("You feel better.", libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)

#This function finds the closest monster within the given range and in the player's field of view.
def closestMonster(maxRange):
	closestEnemy = None
	closestDistance = maxRange + 1
	
	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fovMap, object.x, object.y):
			distance = player.distanceTo(object)
			if distance < closestDistance:
				closestEnemy = object
				closestDistance = distance
	return closestEnemy
	
#This function controls the lightning bolt spell. It finds the closest enemy within a maximum range and
#damages it.
def castLightning():
	monster = closestMonster(LIGHTNING_RANGE)
	if monster is None:
		message("No enemy is close enough to strike.", libtcod.red)
		return "cancel"
	
	message("You unfurl the scroll, and lightning erupts from it! The bolt strikes the " 
		+ monster.name + " for " + str(LIGHTNING_DAMAGE) + " points of damage.", libtcod.light_blue)
	monster.fighter.takeDamage(LIGHTNING_DAMAGE)

def castConfuse():
	#Ask the player for a target to confuse.
	message("Left-click an enemy to confuse it, or right-click to cancel.", libtcod.light_cyan)
	monster = targetMonster(CONFUSE_RANGE)
	if monster is None:
		return "cancel"
	
	#Replace the affected monster's AI with a confused AI.
	oldAI = monster.ai
	monster.ai = ConfusedMonster(oldAI)
	monster.ai.owner = monster
	message("The eyes of the " + monster.name + " look vacant, as it starts to stumble around in a daze.",
		libtcod.light_green) 
	
def targetTile(maxRange = None):
	global key, mouse
	while True:
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
		renderAll()
		
		(x, y) = (mouse.cx, mouse.cy)
		
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fovMap, x, y) 
			and (maxRange is None or player.distance(x,y) <= maxRange)):
			return (x, y)
		
		#Cancel the targeting if the user presses right mouse button or ESC.
		#This must return a tuple of Nones since two variables are needed.
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)
	
#This function asks the player for a target tile 	
def castFireball():
	message("Left-click a target tile for the fireball, or right-click to cancel.", libtcod.light_cyan)
	(x,y) = targetTile()
	if x is None: 
		return "cancel"
	
	message("The fireball explodes, burning everything within " + str(FIREBALL_RADIUS) + " tiles.", 
		libtcod.orange)
	
	for obj in objects:
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message("The " + obj.name + " is burned for " + str(FIREBALL_DAMAGE) + 
				" points of fire damage.", libtcod.orange)
			obj.fighter.takeDamage(FIREBALL_DAMAGE)
	
#This function returns a clicked monster inside the player's field of view up to a range, or None if the
#player right-clicks.
def targetMonster(maxRange = None):
	while True:
		(x, y) = targetTile(maxRange)
		if x is None: #cancelled by player
			return None
		
		#Return the first-clicked monster, otherwise continue looping.
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def startNewGame():
	global player, inventory, messageLog, gameState, dungeonLevel
	
	#Create an object representing the player.
	fighterComponent = Fighter(hp = 100, atk = 4, dfn = 1, xp = 0, deathEffect = playerDeath)
	player = Object(0, 0, gMarked, "player", libtcod.white, True, fighter = fighterComponent)
	
	player.level = 1
	
	#Generate dungeon and FOV maps, although at this point it is not drawn to the screen.
	dungeonLevel = 1
	makeMap()
	initializeFOV()
	
	#Set up the game state and instantiate the player's inventory.
	gameState = "playing"
	inventory = []
	
	#Create the list of game messages and their colors, which begins empty.
	messageLog = []
	message("Welcome, adventurer.", libtcod.red)
	
def initializeFOV():
	global fovNeedsToBeRecomputed, fovMap
	fovNeedsToBeRecomputed = True
	
	#Unexplored areas start black, which is the default background color.
	libtcod.console_clear(con)
	
	#Create the FOV map, according to the generated dungeon map.
	fovMap = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fovMap, x, y, not map[x][y].blockSight, not map[x][y].blocked)

def playGame():
	global key, mouse
	
	playerAction = None
	
	mouse = libtcod.Mouse()
	key = libtcod.Key()
	while not libtcod.console_is_window_closed():
		#Render the screen.
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
		renderAll()
		
		libtcod.console_flush()
		checkLevelup()
		
		#Erase all objects at their old locations, before they move.
		for object in objects:
			object.clear()
			
		#Handle keys and exit the game if needed.
		playerAction = handleKeys()
		if playerAction == "exit":
			saveGame()
			break
		
		#Let monsters take their turn.
		if gameState == "playing" and playerAction != "no turn taken":
			for object in objects:
				if object.ai:
					object.ai.takeTurn()
					
def mainMenu():
	img = libtcod.image_load("menu_background1.png")
	
	while not libtcod.console_is_window_closed():
		#Show the background image, at twice the regular console resolution.
		libtcod.image_blit_2x(img, 0, 0, 0)
		
		#Show the game's title.
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 6, libtcod.BKGND_NONE,
			libtcod.CENTER, "FORCASTIA TALES: THE MARKED")
		libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 4, libtcod.BKGND_NONE,
			libtcod.CENTER, "2014 Studio Draconis")
		
		#Show options and wait for the player's choice.
		choice = menu('', ["Start a New Adventure", "Continue a Previous Adventure", "Quit"], 40)
		
		if choice == 0: #NEW GAME
			startNewGame()
			playGame()
		if choice == 1: #LOAD GAME
			try:
				loadGame()
			except:
				announce("\n No saved game to load. \n", 24)
				continue
			playGame()
		elif choice == 2: #QUIT
			break

#This function saves the game by opening a new, empty Shelve - overwriting an old one if necessary -
#and writing the game data to it.			
def saveGame():
	file = shelve.open("savegame", "n")
	file["map"] = map
	file["objects"] = objects
	file["playerIndex"] = objects.index(player)
	file["inventory"] = inventory
	file["messageLog"] = messageLog
	file["gameState"] = gameState
	file["stairsIndex"] = objects.index(stairsDown)
	file["dungeonLevel"] = dungeonLevel
	file.close()
	
#This function loads a game file by opening a saved shelve.
def loadGame():
	global map, objects, player, inventory, messageLog, gameState, stairsDown, dungeonLevel
	
	file = shelve.open("savegame", "r")
	map = file["map"]
	objects = file["objects"]
	player = objects[file["playerIndex"]]
	inventory = file["inventory"]
	messageLog = file["messageLog"]
	gameState = file["gameState"]
	stairsDown = objects[file["stairsIndex"]]
	dungeonLevel = file["dungeonLevel"]
	file.close()
	
	initializeFOV()
	
#This function announces something using the menu function as an impromptu message box.
def announce(text, width = 50):
	menu(text, [], width)
	
#This function advances to the next level in the dungeon.
def nextLevel():
	global dungeonLevel
	
	message("You take a moment to rest and recover your strength.", libtcod.light_violet)
	player.fighter.heal(player.fighter.hits / 2)
	
	message("After a rare moment of peace, you descend deeper into the heart of the dungeon...", libtcod.red)
	dungeonLevel += 1
	makeMap()
	initializeFOV()
	
#This function watches the player's experience points and controls level ups.
def checkLevelup():
	xpToAdvance = ADVANCE_BASE + player.level * ADVANCE_FACTOR
	if player.fighter.xp >= xpToAdvance:
		player.level += 1
		player.fighter.xp -= xpToAdvance
		message("You have advanced to courage level " + str(player.level) + ".", libtcod.yellow)
		
		#Present the player with a choice of skills to increase
		choice = None
		while choice == None: #Keep asking until a choice is made.
			choice = menu("Your skills are admirable, Marked. Tell me, how do you feel?\n",
				["Tougher (+20 HP, from " + str(player.fighter.hits) + ")",
				"Stronger (+1 Attack, from " + str(player.fighter.atk) + ")",
				"Faster (+1 Defense, from " + str(player.fighter.dfn) + ")"], ADVANCE_MENU_WIDTH)
			
			if choice == 0:
				player.fighter.hits += 20
				player.fighter.cond += 20
			elif choice == 1:
				player.fighter.atk += 1
			elif choice == 2:
				player.fighter.dfn += 1
				
#This function chooses one option from a list of chances, returning its index. The dice will land 
#on some number between one and the sum of the chances.
def randomChoiceIndex(chances):
	dice = libtcod.random_get_int(0, 1, sum(chances))
	
	#Go through all chances, keeping the sum so far.
	runningSum = 0
	choice = 0
	for w in chances:
		runningSum += w
		
		#See if the dice landed in the part that corresponds to this choice.
		if dice <= runningSum:
			return choice
		choice += 1

#This function chooses one option randomly from a dictionary of choices, returning its key.
def chooseFromDict(possibilityDictionary):
	chances = possibilityDictionary.values()
	possibilities = possibilityDictionary.keys()
	
	return possibilities[randomChoiceIndex(chances)]
	
#This function returns the equipment in a given slot, or None if it is empty.
def getEquippedInSlot(slot):
	for obj in inventory:
		if object.equipment and object.equipment.slot == slot and object.equipment.isWorn:
			return obj.equipment
	return None

#This function returns a value that depends on level. The table's pairs are in the format [value, level]. The table specifies what value occurs after each level, default is zero. This function uses the REVERSED function from the Python standard library. Attempting to loop in the regular order will always return the value on the first element. This function assumes that the table sorted by level in ascending order, but it is possible to enforce this strictly with the sort function.
def fromDungeonLevel(table):
	for(value, level) in reversed(table):
		if dungeonLevel >= level:
			return value
	return 0

#########################################################################################################
#Initialize the consoles, font style, and FPS limit.
libtcod.console_set_custom_font('terminal8x8_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Forcastia Tales', False)
libtcod.sys_set_fps(FPS_LIMIT)

con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

mainMenu()
		
#random_get_int returns a random number between two numbers, the second and third parameters. The first
#parameter identifies the "stream" to get that number from. Random number streams are used for recreating
#sequences of random numbers. 0 is the default stream.