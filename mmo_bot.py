import discord
from discord.ext import commands
import random
import json
import os

# ==============================
# CONFIG
# ==============================

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("No se encontró el token. Configura DISCORD_TOKEN en las variables de entorno.")
DATA_FILE = "players.json"
K_FACTOR = 32

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================
# DATA MANAGEMENT
# ==============================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ==============================
# PLAYER SYSTEM
# ==============================

def create_player(clase):
    base = {
        "clase": clase,
        "nivel": 1,
        "xp": 0,
        "oro": 100,
        "victorias": 0,
        "historia": 1,
        "elo": 1000
    }

    if clase == "guerrero":
        base.update({"vida": 140, "max_vida": 140, "daño": 18})
    elif clase == "mago":
        base.update({"vida": 90, "max_vida": 90, "daño": 25})
    elif clase == "asesino":
        base.update({"vida": 110, "max_vida": 110, "daño": 22})
    else:
        return None

    return base

def level_up(player):
    required = player["nivel"] * 100
    if player["xp"] >= required:
        player["nivel"] += 1
        player["xp"] = 0
        player["max_vida"] += 20
        player["vida"] = player["max_vida"]
        player["daño"] += 5
        return True
    return False

# ==============================
# ELO SYSTEM
# ==============================

def calcular_elo(elo1, elo2, resultado):
    expectativa = 1 / (1 + 10 ** ((elo2 - elo1) / 400))
    return round(elo1 + K_FACTOR * (resultado - expectativa))

# ==============================
# COMMANDS
# ==============================

@bot.command()
async def crear(ctx, clase: str):
    clase = clase.lower()
    data = load_data()
    user = str(ctx.author.id)

    if user in data:
        return await ctx.send("⚠ Ya tienes personaje.")

    player = create_player(clase)
    if not player:
        return await ctx.send("Clases disponibles: guerrero, mago, asesino")

    data[user] = player
    save_data(data)

    await ctx.send(f"🎉 {ctx.author.name} ahora es {clase.upper()}!")

@bot.command()
async def perfil(ctx):
    data = load_data()
    user = str(ctx.author.id)

    if user not in data:
        return await ctx.send("❌ Usa !crear primero")

    p = data[user]

    embed = discord.Embed(title=f"🧙 {ctx.author.name}", color=0x00ff99)
    embed.add_field(name="Clase", value=p["clase"])
    embed.add_field(name="Nivel", value=p["nivel"])
    embed.add_field(name="Vida", value=f"{p['vida']}/{p['max_vida']}")
    embed.add_field(name="Daño", value=p["daño"])
    embed.add_field(name="XP", value=p["xp"])
    embed.add_field(name="Historia", value=f"Capítulo {p['historia']}")
    embed.add_field(name="Victorias PvP", value=p["victorias"])
    embed.add_field(name="ELO", value=p["elo"])

    await ctx.send(embed=embed)

# ==============================
# PVE - HISTORIA
# ==============================

@bot.command()
async def historia(ctx):
    data = load_data()
    user = str(ctx.author.id)

    if user not in data:
        return await ctx.send("❌ Crea personaje primero.")

    player = data[user]
    cap = player["historia"]

    enemigo_vida = 50 + cap * 25
    enemigo_daño = 10 + cap * 6

    await ctx.send(f"📖 Capítulo {cap}\n👾 Enemigo: ❤️ {enemigo_vida} | ⚔ {enemigo_daño}")

    vida_jugador = player["vida"]

    while enemigo_vida > 0 and vida_jugador > 0:
        enemigo_vida -= player["daño"]
        vida_jugador -= enemigo_daño

    if vida_jugador <= 0:
        player["vida"] = player["max_vida"]
        save_data(data)
        return await ctx.send("💀 Has sido derrotado. Intenta nuevamente.")

    xp = 50 + cap * 15
    player["xp"] += xp
    player["historia"] += 1
    player["vida"] = player["max_vida"]

    subio = level_up(player)
    save_data(data)

    msg = f"🏆 Capítulo completado! +{xp} XP"
    if subio:
        msg += "\n🎉 Subiste de nivel!"

    await ctx.send(msg)

# ==============================
# PVP RANKED
# ==============================

@bot.command()
async def pvp(ctx, rival: discord.Member):
    data = load_data()
    user1 = str(ctx.author.id)
    user2 = str(rival.id)

    if user1 not in data or user2 not in data:
        return await ctx.send("Ambos jugadores necesitan personaje.")

    if user1 == user2:
        return await ctx.send("No puedes pelear contra ti mismo.")

    p1 = data[user1]
    p2 = data[user2]

    vida1 = p1["max_vida"]
    vida2 = p2["max_vida"]

    await ctx.send(
        f"⚔ RANKED ⚔\n"
        f"{ctx.author.name} ({p1['elo']} ELO) vs {rival.name} ({p2['elo']} ELO)"
    )

    turno = 1
    while vida1 > 0 and vida2 > 0:
        if turno % 2 == 1:
            daño = random.randint(p1["daño"] - 5, p1["daño"] + 5)
            vida2 -= daño
        else:
            daño = random.randint(p2["daño"] - 5, p2["daño"] + 5)
            vida1 -= daño
        turno += 1

    if vida1 > 0:
        ganador = ctx.author
        p1["victorias"] += 1
        nuevo1 = calcular_elo(p1["elo"], p2["elo"], 1)
        nuevo2 = calcular_elo(p2["elo"], p1["elo"], 0)
    else:
        ganador = rival
        p2["victorias"] += 1
        nuevo1 = calcular_elo(p1["elo"], p2["elo"], 0)
        nuevo2 = calcular_elo(p2["elo"], p1["elo"], 1)

    cambio1 = nuevo1 - p1["elo"]
    cambio2 = nuevo2 - p2["elo"]

    p1["elo"] = nuevo1
    p2["elo"] = nuevo2

    save_data(data)

    await ctx.send(
        f"🏆 Ganador: {ganador.name}\n\n"
        f"{ctx.author.name}: {p1['elo']} ({'+' if cambio1>=0 else ''}{cambio1})\n"
        f"{rival.name}: {p2['elo']} ({'+' if cambio2>=0 else ''}{cambio2})"
    )

# ==============================
# RANKING
# ==============================

@bot.command()
async def ranking(ctx):
    data = load_data()
    ranking = sorted(data.items(), key=lambda x: x[1]["elo"], reverse=True)

    mensaje = "🏆 RANKING GLOBAL (ELO)\n\n"

    for i, (user_id, stats) in enumerate(ranking[:10], start=1):
        user = await bot.fetch_user(int(user_id))
        mensaje += f"{i}. {user.name} - {stats['elo']} ELO\n"

    await ctx.send(mensaje)

# ==============================


bot.run(TOKEN)
