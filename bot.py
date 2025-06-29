import os
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from discord.ext.commands import CommandNotFound
import re

TOKEN = os.getenv("DISCORD_TOKEN")
URI = os.getenv("MONGO_URI")

## check for TOKEN
if not TOKEN:
    raise RuntimeError("MISSING Discord Token")

mongo = AsyncIOMotorClient(URI)
db = mongo["zetdb"] # use explicitly to handle TLS issues
print("db type:", type(db))
print("collection type:", type(db.units))

## grab collections from mongo
scol = db.skills
ecol = db.equip
wcol = db.weapons
pcol = db.periph

#set up bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# signals boy is logged in and ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

async def lookup_unit(ctx, query: str):
   # first try exact match
   unit = await db.units.find_one({"name": {"$regex": f"^{re.escape(query)}$", "$options": "i"}})

   # then try fuzzy search
   if not unit:
    unit = await db.units.find_one({"name": {"$regex": f"{re.escape(query)}", "$options": "i"}})

   # else, found nothing
   if not unit:
        return await ctx.send(f"❓ No unit found matching `{query}`.")
   
   #grab units first profile TODO: fix to work for units with more than one profile
   prof = unit["profileGroups"][0]["profiles"][0]
   
   uDoc = await db.type.find_one({"id": (unit['profileGroups'][0]['profiles'][0]['type'])})
   uType = uDoc["name"] if uDoc else "Unknown Type"
   uDoc2 = await db.category.find_one({"id": (unit['profileGroups'][0]['category'])})
   uCat = uDoc2["name"] if uDoc2 else "Unknown Category"
   
   # Build an embed
   embed = discord.Embed(
        title=unit["name"],
        #description="Test",
        description=f"{uType}, {uCat}",
        color=discord.Color.blue()
    )
   embed.set_thumbnail(url=prof["logo"])
   print(prof["logo"])
   
   embed.add_field(name="🛡 ARM",   value=prof["arm"],   inline=True)
   embed.add_field(name="🥽 BTS",   value=prof["bts"],   inline=True)
   embed.add_field(name="🎯 BS",    value=prof["bs"],    inline=True)
   embed.add_field(name="⚔️ CC",    value=prof["cc"],    inline=True)
   embed.add_field(name="🧠 WIP",   value=prof["wip"],   inline=True)
   embed.add_field(name="💪 PH",    value=prof["ph"],    inline=True)
   embed.add_field(name="🚶 MOV",   value=f"{prof['move'][0]}-{prof['move'][1]}", inline=True)
   embed.add_field(name="❤️ W/STR",     value=prof["w"],     inline=True)

   ## get base skills, equipment, characteristics, peripherals
   skill_ids = [s["id"] for s in prof['skills']] # use list comprehension
   skills = await db.skills.find({"id": {"$in": skill_ids}}).to_list(None)
   sknames = [s["name"] for s in skills]

   # Get peripheral names
   pids = [str(p["id"]) for p in prof.get("peripherals", [])]
   periph_docs = await db.periph.find({"id": {"$in": pids}}).to_list(None)
   pernames = [p["name"] for p in periph_docs]

   eids = [e["id"] for e in prof["equip"]]
   equip_docs = await db.equip.find({"id": {"$in": eids}}).to_list(None)
   eqnames = [e["name"] for e in equip_docs]

   cids = [c for c in prof["chars"]]
   cdocs = await db.chars.find({"id": {"$in": cids}}).to_list(None)
   chnames = [c["name"] for c in cdocs]

   value_parts = []

   if chnames:
        value_parts.append(f"**Characteristics:** {', '.join(chnames)}")

   if sknames:
        value_parts.append(f"**Skills:** {', '.join(sknames)}")

   if eqnames:
        value_parts.append(f"**Equipment:** {', '.join(eqnames)}")

   if pernames:
        value_parts.append(f"**Peripherals:** {', '.join(pernames)}")

   value = "\n".join(value_parts)


   embed.add_field(name="Base Profile", value=value, inline=False)

   # profile divider
   embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━━━━", inline=False)

   #iterate through profile options
   i = 0 # counter
   options = unit["profileGroups"][0]["options"]
   for o in options:
       i += 1 
       skill_ids = [s["id"] for s in o['skills']] # use list comprehension
       skills = await db.skills.find({"id": {"$in": skill_ids}}).to_list(None)
       snames = [s["name"] for s in skills]

       weapon_ids = [w["id"] for w in o.get("weapons", []) if "id" in w] # use list comprehension, added extra code to handle error cases
       weapons = await db.weapons.find({"id": {"$in": weapon_ids}}).to_list(None)
       wnames = [w["name"] for w in weapons]


       # Get peripheral names
       pids = [str(p["id"]) for p in o.get("peripherals", [])]
       periph_docs = await db.periph.find({"id": {"$in": pids}}).to_list(None)
       pnames = [p["name"] for p in periph_docs]

       eids = [e["id"] for e in o["equip"]]
       equip_docs = await db.equip.find({"id": {"$in": eids}}).to_list(None)
       enames = [e["name"] for e in equip_docs]

       lines = []

       if snames:
           lines.append(f"**Skills:** {', '.join(snames)}")

       if enames:
           lines.append(f"**Equipment:** {', '.join(enames)}")

       if wnames:
           lines.append(f"**Weapons:** {', '.join(wnames)}")

       if pnames:
           lines.append(f"**Peripherals:** {', '.join(pnames)}")

       # Always add cost
       lines.append(f"**Cost:** {o['points']} pts")

       # Optional: Add separator if you like
       lines.append(f"-------------------")

       # Combine all the lines into one string
       value = "\n".join(lines)


       embed.add_field(name=f"Profile {i}", value=value, inline=False)
       '''
       #aggregate necessary values
       sids = o.get("skills",[])
       wids = o.get("weapons",[])
       eids = o.get("equip",[])
       pids = o.get("peripheral",[])

       #use ids to fetch names of data
       skills = await scol.find({"id": {"$in": sids}}).to_list(None)
       equipment = await ecol.find({"id": {"$in": eids}}).to_list(None)
       weapons = await wcol.find({"id": {"$in": wids}}).to_list(None) 
       peripherals = await pcol.find({"id": {"$in": pids}}).to_list(None)

       #extract names from the data
       snames = [s["name"] for s in skills]
       enames = [e["name"] for e in equipment]
       wnames = [w["name"] for w in weapons]
       pnames = [p["name"] for p in peripherals]

       # build value for embed
       value = (
        f"**Skills:** {', '.join(snames)}\n"
        f"**Equipment:** {', '.join(enames)}\n"
        f"**Weapons:** {', '.join(wnames)}\n"
        #f"**Peripherals:**{', '.joing(pnames)}\n"
        f"**Cost:** {o['points']} pts"
       )

       embed.add_field(name=o["name"], value=value, inline=False)
       '''


       #name, might be needed for FTO profiles, yet useless for all else?

       #weapons
       
       #eq

       #skills

       #peri,if exists

       # points 

   await ctx.send(embed=embed)

@bot.command(name="unit", help="Lookup a unit by name or ID")
async def unit_cmd(ctx, *, query: str):
    await lookup_unit(ctx, query)

#fall back to enable !Ajax to search ajax
@bot.event
async def on_command_error(ctx, error):
    # If they typed !Something that isn't a command...
    if isinstance(error, CommandNotFound):
        text = ctx.message.content.lstrip("!")  # strip the bang
        await lookup_unit(ctx, text)            # treat it as a unit name
    else:
        # let other errors bubble up
        raise error


bot.run(TOKEN)