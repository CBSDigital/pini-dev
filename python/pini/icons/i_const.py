"""Constants for the icons library."""

import logging
import os

import pini_icons
from pini.utils import abs_path, Dir

from . import i_set

_LOGGER = logging.getLogger(__name__)

ICONS_ROOT = os.environ.get(
    'PINI_ICONS_ROOT',
    Dir(abs_path(pini_icons.__file__)).to_dir().to_dir().path)

_ANDROID_PATH = Dir(ICONS_ROOT).to_file(
    'icons/android_12l/icon.%04d.png')
ANDROID = i_set.EmojiSet(_ANDROID_PATH)

_JOYPIXELS_PATH = Dir(ICONS_ROOT).to_file(
    'icons/joypixels_4.5/icon.%04d.png')
_JOYPIXELS = i_set.EmojiSet(_JOYPIXELS_PATH)

_OPENMOJI_PATH = Dir(ICONS_ROOT).to_file(
    'icons/openmoji_13.1/icon.%04d.png')
_OPENMOJI = i_set.EmojiSet(_OPENMOJI_PATH)

EMOJI = ANDROID

_FRUIT = (
    'Grapes', 'Melon', 'Watermelon', 'Tangerine', 'Lemon', 'Banana',
    'Pineapple', 'Mango', 'Red Apple', 'Green Apple', 'Pear',
    'Peach', 'Cherries', 'Strawberry', 'Blueberries', 'Kiwi Fruit',
    'Tomato', 'Olive', 'Coconut', 'Avocado', 'Eggplant', 'Potato', 'Carrot',
    'Ear of Corn', 'Hot Pepper', 'Bell Pepper', 'Cucumber', 'Leafy Green',
    'Broccoli', 'Garlic', 'Onion', 'Mushroom', 'Peanuts', 'Chestnut')
FRUIT_NAMES = _FRUIT

_ANIMAL_FACES = (
    'Monkey Face', 'Dog Face', 'Wolf', 'Fox', 'Cat Face', 'Lion',
    'Tiger Face', 'Cow Face', 'Pig Face', 'Mouse Face', 'Hamster',
    'Rabbit Face', 'Bat', 'Bear', 'Panda', 'Chicken', 'Baby Chick',
    'Peacock', 'Frog', 'Snake', 'Dragon Face')
ANIMAL_FACES_NAMES = _ANIMAL_FACES

_COOL = (
    'Clown Face', 'Ghost', 'Alien', 'Robot', 'Grinning Cat',
    'Hand with Fingers Splayed: Medium-Dark Skin Tone', 'Genie', 'Man Genie',
    'Woman Genie', 'Orangutan', 'Baby Chick', 'Peacock', 'Frog', 'Octopus',
    'Spiral Shell', 'Ant', 'Spider', 'Spider Web', 'Scorpion', 'Fly',
    'Microbe', 'Bouquet', 'Cherry Blossom', 'White Flower', 'Rosette',
    'Rose', 'Wilted Flower', 'Hibiscus', 'Sunflower', 'Blossom', 'Tulip',
    'Seedling', 'Potted Plant', 'Evergreen Tree', 'Deciduous Tree',
    'Palm Tree', 'Cactus', 'Sheaf of Rice', 'Herb', 'Shamrock',
    'Four Leaf Clover', 'Maple Leaf', 'Fallen Leaf',
    'Leaf Fluttering in Wind', 'Chestnut', 'Bread', 'Croissant',
    'Pretzel', 'Cheese Wedge', 'Shaved Ice', 'Doughnut', 'Cookie',
    'Cupcake', 'Custard', 'Wood', 'Hut', 'House', 'Parachute', 'Rocket',
    'Flying Saucer', 'New Moon', 'Waxing Crescent Moon',
    'First Quarter Moon', 'Waxing Gibbous Moon', 'Full Moon',
    'Waning Gibbous Moon', 'Last Quarter Moon', 'Waning Crescent Moon',
    'New Moon Face', 'Sun with Face', 'Ringed Planet', 'Rainbow',
    'Droplet', 'Jack-O-Lantern', 'Balloon', 'Party Popper',
    'Tanabata Tree', 'Pine Decoration', 'Japanese Dolls',
    'Carp Streamer', 'Wind Chime', 'Moon Viewing Ceremony',
    'Red Envelope', 'Ribbon', 'Wrapped Gift', 'Admission Tickets',
    'Soccer Ball', 'Baseball', 'Softball', 'Basketball', 'Volleyball',
    'American Football', 'Rugby Football', 'Tennis', 'Flying Disc',
    'Pool 8 Ball', 'Crystal Ball', 'Nazar Amulet', 'Slot Machine',
    'Game Die', 'Puzzle Piece', 'Teddy Bear', 'Pinata', 'Nesting Dolls',
    'Spade Suit', 'Heart Suit', 'Diamond Suit', 'Club Suit', 'Chess Pawn',
    'Joker', 'Mahjong Red Dragon', 'Flower Playing Cards', 'Performing Arts',
    'Framed Picture', 'Yarn', 'Gem Stone', 'Long Drum', 'Optical Disk',
    'Abacus', 'Red Paper Lantern', 'Paintbrush', 'Crayon', 'Pill', 'Soap',
    'Fire Extinguisher', 'Atom Symbol', 'Yin Yang', 'Peace Symbol',
    'Bright Button', 'Fleur-de-lis', 'Trident Emblem', 'Hollow Red Circle',
    'Red Circle', 'Orange Circle', 'Yellow Circle', 'Green Circle',
    'Blue Circle', 'Purple Circle', 'Brown Circle', 'Black Circle',
    'White Circle')
COOL_NAMES = _COOL

_FOODS = [
    'Bread', 'Croissant', 'Baguette Bread', 'Flatbread', 'Pretzel', 'Bagel',
    'Pancakes', 'Waffle', 'Cheese Wedge', 'Meat on Bone', 'Poultry Leg',
    'Cut of Meat', 'Bacon', 'Hamburger', 'French Fries', 'Pizza', 'Hot Dog',
    'Sandwich', 'Taco', 'Burrito', 'Tamale', 'Stuffed Flatbread', 'Falafel',
    'Egg', 'Cooking', 'Shallow Pan of Food', 'Pot of Food', 'Fondue',
    'Bowl with Spoon', 'Green Salad', 'Popcorn', 'Butter', 'Salt',
    'Canned Food', 'Bento Box', 'Rice Cracker', 'Rice Ball', 'Cooked Rice',
    'Curry Rice', 'Steaming Bowl', 'Spaghetti', 'Roasted Sweet Potato',
    'Oden', 'Sushi', 'Fried Shrimp', 'Fish Cake with Swirl', 'Moon Cake',
    'Dango', 'Dumpling', 'Fortune Cookie', 'Takeout Box', 'Crab', 'Lobster',
    'Shrimp', 'Squid', 'Oyster', 'Soft Ice Cream', 'Shaved Ice', 'Ice Cream',
    'Doughnut', 'Cookie', 'Birthday Cake', 'Shortcake', 'Cupcake', 'Pie',
    'Chocolate Bar', 'Candy', 'Lollipop', 'Custard', 'Honey Pot']
FOOD_NAMES = _FOODS

_FLORA = [
    'Bouquet', 'Cherry Blossom', 'White Flower', 'Rosette', 'Rose',
    'Wilted Flower', 'Hibiscus', 'Sunflower', 'Blossom', 'Tulip', 'Seedling',
    'Potted Plant', 'Evergreen Tree', 'Deciduous Tree', 'Palm Tree', 'Cactus',
    'Sheaf of Rice', 'Herb', 'Shamrock', 'Four Leaf Clover', 'Maple Leaf',
    'Fallen Leaf', 'Leaf Fluttering in Wind']
FLORA_NAMES = _FLORA

_ANIMALS = [
    'Monkey Face', 'Monkey', 'Gorilla', 'Orangutan', 'Dog Face', 'Dog',
    'Guide Dog', 'Service Dog', 'Poodle', 'Wolf', 'Fox', 'Raccoon',
    'Cat Face', 'Cat', 'Black Cat', 'Lion', 'Tiger Face', 'Tiger', 'Leopard',
    'Horse Face', 'Horse', 'Unicorn', 'Zebra', 'Deer', 'Bison', 'Cow Face',
    'Ox', 'Water Buffalo', 'Cow', 'Pig Face', 'Pig', 'Boar', 'Pig Nose',
    'Ram', 'Ewe', 'Goat', 'Camel', 'Two-Hump Camel', 'Llama', 'Giraffe',
    'Elephant', 'Mammoth', 'Rhinoceros', 'Hippopotamus', 'Mouse Face',
    'Mouse', 'Rat', 'Hamster', 'Rabbit Face', 'Rabbit', 'Chipmunk', 'Beaver',
    'Hedgehog', 'Bat', 'Bear', 'Polar Bear', 'Koala', 'Panda', 'Sloth',
    'Otter', 'Skunk', 'Kangaroo', 'Badger', 'Paw Prints', 'Turkey', 'Chicken',
    'Rooster', 'Hatching Chick', 'Baby Chick', 'Front-Facing Baby Chick',
    'Bird', 'Penguin', 'Dove', 'Eagle', 'Duck', 'Swan', 'Owl', 'Dodo',
    'Feather', 'Flamingo', 'Peacock', 'Parrot', 'Frog', 'Crocodile', 'Turtle',
    'Lizard', 'Snake', 'Dragon Face', 'Dragon', 'Sauropod', 'T-Rex',
    'Spouting Whale', 'Whale', 'Dolphin', 'Seal', 'Fish', 'Tropical Fish',
    'Blowfish', 'Shark', 'Octopus', 'Spiral Shell', 'Snail', 'Butterfly',
    'Bug', 'Ant', 'Honeybee', 'Beetle', 'Lady Beetle', 'Cricket', 'Cockroach',
    'Spider', 'Spider Web', 'Scorpion', 'Mosquito', 'Fly', 'Worm', 'Microbe']
ANIMAL_NAMES = _ANIMALS

_HANDS = [
    'Waving Hand',
    'Raised Back of Hand',
    'Hand with Fingers Splayed',
    'Raised Hand',
    'Vulcan Salute',
    'OK Hand',
    'Pinched Fingers',
    'Pinching Hand',
    'Victory Hand',
    'Crossed Fingers',
    'Love-You Gesture',
    'Sign of the Horns',
    'Call Me Hand',
    'Backhand Index Pointing Left',
    'Backhand Index Pointing Right',
    'Backhand Index Pointing Up',
    'Middle Finger',
    'Backhand Index Pointing Down',
    'Index Pointing Up',
    'Thumbs Up',
    'Thumbs Down',
    'Raised Fist',
    'Oncoming Fist',
    'Left-Facing Fist',
    'Right-Facing Fist',
    'Clapping Hands',
    'Raising Hands',
    'Open Hands',
    'Palms Up Together',
    'Folded Hands',
    'Writing Hand',
    'Nail Polish',
    'Selfie',
    'Flexed Biceps',
    'Leg',
    'Foot',
    'Ear',
    'Ear with Hearing Aid',
    'Nose']
HAND_NAMES = _HANDS

_PEOPLE = [
    'Baby',
    'Child',
    'Boy',
    'Girl',
    'Person',
    'Man',
    'Woman',
    'Older Person',
    'Old Man',
    'Old Woman',
    'Person Frowning',
    'Man Frowning',
    'Woman Frowning',
    'Person Pouting',
    'Man Pouting',
    'Woman Pouting',
    'Person Gesturing No',
    'Man Gesturing No',
    'Woman Gesturing No',
    'Person Gesturing OK',
    'Man Gesturing OK',
    'Woman Gesturing OK',
    'Person Tipping Hand',
    'Man Tipping Hand',
    'Woman Tipping Hand',
    'Person Raising Hand',
    'Man Raising Hand',
    'Woman Raising Hand',
    'Deaf Person',
    'Deaf Man',
    'Deaf Woman',
    'Person Bowing',
    'Man Bowing',
    'Woman Bowing',
    'Person Facepalming',
    'Man Facepalming',
    'Woman Facepalming',
    'Person Shrugging',
    'Man Shrugging',
    'Woman Shrugging',
    'Health Worker',
    'Man Health Worker',
    'Woman Health Worker',
    'Student',
    'Man Student',
    'Woman Student',
    'Teacher',
    'Man Teacher',
    'Woman Teacher',
    'Judge',
    'Man Judge',
    'Woman Judge',
    'Farmer',
    'Man Farmer',
    'Woman Farmer',
    'Cook',
    'Man Cook',
    'Woman Cook',
    'Mechanic',
    'Man Mechanic',
    'Woman Mechanic',
    'Factory Worker',
    'Man Factory Worker',
    'Woman Factory Worker',
    'Office Worker',
    'Man Office Worker',
    'Woman Office Worker',
    'Scientist',
    'Man Scientist',
    'Woman Scientist',
    'Technologist',
    'Man Technologist',
    'Woman Technologist',
    'Singer',
    'Man Singer',
    'Woman Singer',
    'Artist',
    'Man Artist',
    'Woman Artist',
    'Pilot',
    'Man Pilot',
    'Woman Pilot',
    'Astronaut',
    'Man Astronaut',
    'Woman Astronaut',
    'Firefighter',
    'Man Firefighter',
    'Woman Firefighter',
    'Police Officer',
    'Man Police Officer',
    'Woman Police Officer',
    'Detective',
    'Man Detective',
    'Woman Detective',
    'Guard',
    'Man Guard',
    'Woman Guard',
    'Ninja',
    'Construction Worker',
    'Man Construction Worker',
    'Woman Construction Worker',
    'Prince',
    'Princess',
    'Person Wearing Turban',
    'Man Wearing Turban',
    'Woman Wearing Turban',
    'Person With Skullcap',
    'Woman with Headscarf',
    'Person in Tuxedo',
    'Man in Tuxedo',
    'Woman in Tuxedo',
    'Person With Veil',
    'Man with Veil',
    'Woman with Veil',
    'Pregnant Woman',
    'Breast-Feeding',
    'Woman Feeding Baby',
    'Man Feeding Baby',
    'Person Feeding Baby',
    'Baby Angel',
    'Santa Claus',
    'Mrs. Claus',
    'Mx Claus',
    'Superhero',
    'Man Superhero',
    'Woman Superhero',
    'Supervillain',
    'Man Supervillain',
    'Woman Supervillain',
    'Mage',
    'Man Mage',
    'Woman Mage',
    'Fairy',
    'Man Fairy',
    'Woman Fairy',
    'Vampire',
    'Man Vampire',
    'Woman Vampire',
    'Merperson',
    'Merman',
    'Mermaid',
    'Elf',
    'Man Elf',
    'Woman Elf',
    'Person Getting Massage',
    'Man Getting Massage',
    'Woman Getting Massage',
    'Person Getting Haircut',
    'Man Getting Haircut',
    'Woman Getting Haircut',
    'Person Walking',
    'Man Walking',
    'Woman Walking',
    'Person Standing',
    'Man Standing',
    'Woman Standing',
    'Person Kneeling',
    'Man Kneeling',
    'Woman Kneeling',
    'Person with White Cane',
    'Man with White Cane',
    'Woman with White Cane',
    'Person in Motorized Wheelchair',
    'Man in Motorized Wheelchair',
    'Woman in Motorized Wheelchair',
    'Person in Manual Wheelchair',
    'Man in Manual Wheelchair',
    'Woman in Manual Wheelchair',
    'Person Running',
    'Man Running',
    'Woman Running',
    'Woman Dancing',
    'Man Dancing',
    'Person in Suit Levitating',
    'Person in Steamy Room',
    'Man in Steamy Room',
    'Woman in Steamy Room',
    'Person Climbing',
    'Man Climbing',
    'Woman Climbing',
    'Horse Racing',
    'Snowboarder',
    'Person Golfing',
    'Man Golfing',
    'Woman Golfing',
    'Person Surfing',
    'Man Surfing',
    'Woman Surfing',
    'Person Rowing Boat',
    'Man Rowing Boat',
    'Woman Rowing Boat',
    'Person Swimming',
    'Man Swimming',
    'Woman Swimming',
    'Person Bouncing Ball',
    'Man Bouncing Ball',
    'Woman Bouncing Ball',
    'Person Lifting Weights',
    'Man Lifting Weights',
    'Woman Lifting Weights',
    'Person Biking',
    'Man Biking',
    'Woman Biking',
    'Person Mountain Biking',
    'Man Mountain Biking',
    'Woman Mountain Biking',
    'Person Cartwheeling',
    'Man Cartwheeling',
    'Woman Cartwheeling',
    'Person Playing Water Polo',
    'Man Playing Water Polo',
    'Woman Playing Water Polo',
    'Person Playing Handball',
    'Man Playing Handball',
    'Woman Playing Handball',
    'Person Juggling',
    'Man Juggling',
    'Woman Juggling',
    'Person in Lotus Position',
    'Man in Lotus Position',
    'Woman in Lotus Position',
    'Person Taking Bath',
    'Person in Bed',
    'People Holding Hands',
    'Women Holding Hands',
    'Woman and Man Holding Hands',
    'Men Holding Hands',
    'Kiss',
    'Couple with Heart']
PEOPLE_NAMES = _PEOPLE

_SKINS = _HANDS + _PEOPLE
SKIN_NAMES = _SKINS

SKIN_TONES = (
    'Light Skin Tone',
    'Medium-Light Skin Tone',
    'Medium Skin Tone',
    'Medium-Dark Skin Tone',
    'Dark Skin Tone')

BUILD = EMOJI.find('Hammer')
BROWSER = EMOJI.find('Open File Folder')
COPY = EMOJI.find('Spiral Notepad')
CLEAN = EMOJI.find('Sponge')
CLEAR = EMOJI.find('Cross Mark Button')
DELETE = EMOJI.find('No Entry')
DUPLICATE = EMOJI.find('Busts in Silhouette')
EDIT = EMOJI.find('Pencil')
FILTER = EMOJI.find('Oil Drum')
FIND = EMOJI.find('Magnifying Glass Tilted Right')
LOAD = EMOJI.find('Outbox Tray')
LOCKED = EMOJI.find('Locked')
PRINT = EMOJI.find('Downwards Button')
REFRESH = EMOJI.find('Counterclockwise Arrows Button')
RESET = EMOJI.find('Broom')
SAVE = EMOJI.find('Floppy Disk')
SELECT = EMOJI.find('Down-Left Arrow')
TEST = EMOJI.find('Alembic')
UNLOCKED = EMOJI.find('Unlocked')
URL = EMOJI.find('Globe Showing Europe-Africa')

FRUIT = EMOJI.find_grp('fruit')
COOL = EMOJI.find_grp('cool')

MOONS = [EMOJI.find(_name) for _name in (
    'New Moon',
    'Waxing Crescent Moon',
    'First Quarter Moon',
    'Waxing Gibbous Moon',
    'Full Moon',
)]
