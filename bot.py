import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
APPLICATION_CHANNEL_ID = os.getenv("APPLICATION_CHANNEL_ID")  # optional

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========== DATABASE ==========
def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    team_name TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# ========== BUTTONS ==========
class ApplicationView(View):
    def __init__(self, applicant_id, team_name):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.team_name = team_name

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Only staff can do this.", ephemeral=True)

        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("UPDATE applications SET status = 'accepted' WHERE user_id = ? AND team_name = ?",
                  (self.applicant_id, self.team_name))
        c.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (self.team_name,))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"✅ Application for **{self.team_name}** accepted by {interaction.user.mention}")
        self.stop()

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Only staff can do this.", ephemeral=True)

        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("UPDATE applications SET status = 'denied' WHERE user_id = ? AND team_name = ?",
                  (self.applicant_id, self.team_name))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"❌ Application for **{self.team_name}** denied by {interaction.user.mention}")
        self.stop()

# ========== EVENTS ==========
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Premier Esports League Bot is online!")

# ========== COMMANDS ==========
@bot.command()
async def apply(ctx, *, team_name: str):
    """Apply to create/join a team"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT INTO applications (user_id, username, team_name, created_at) VALUES (?, ?, ?, ?)",
              (ctx.author.id, str(ctx.author), team_name, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="New Team Application",
        description=f"**Team:** {team_name}\n**Applicant:** {ctx.author.mention}",
        color=discord.Color.blue()
    )

    view = ApplicationView(ctx.author.id, team_name)

    # Send to application channel if set, otherwise in current channel
    if APPLICATION_CHANNEL_ID:
        channel = bot.get_channel(int(APPLICATION_CHANNEL_ID))
        if channel:
            await channel.send(embed=embed, view=view)
            await ctx.send("✅ Your application has been sent to staff!")
            return

    await ctx.send(embed=embed, view=view)

@bot.command()
async def standings(ctx):
    """Show current league standings"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT name, wins, losses FROM teams ORDER BY wins DESC, losses ASC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        return await ctx.send("No teams registered yet.")

    description = ""
    for i, (name, wins, losses) in enumerate(rows, 1):
        description += f"**{i}. {name}** — {wins}W / {losses}L\n"

    embed = discord.Embed(title="Premier Esports League Standings", description=description, color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_guild=True)
async def result(ctx, team1: str, score1: int, team2: str, score2: int):
    """Record a match result (Staff only)  Example: !result TeamA 2 TeamB 1"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()

    # Update wins/losses
    if score1 > score2:
        c.execute("UPDATE teams SET wins = wins + 1 WHERE name = ?", (team1,))
        c.execute("UPDATE teams SET losses = losses + 1 WHERE name = ?", (team2,))
    else:
        c.execute("UPDATE teams SET wins = wins + 1 WHERE name = ?", (team2,))
        c.execute("UPDATE teams SET losses = losses + 1 WHERE name = ?", (team1,))

    conn.commit()
    conn.close()

    await ctx.send(f"✅ Result recorded: **{team1} {score1} - {score2} {team2}**")

@bot.command()
async def teams(ctx):
    """List all registered teams"""
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT name FROM teams ORDER BY name")
    rows = c.fetchall()
    conn.close()

    if not rows:
        return await ctx.send("No teams yet.")

    team_list = "\n".join(f"• {row[0]}" for row in rows)
    embed = discord.Embed(title="Registered Teams", description=team_list, color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")

# ========== START ==========
if not TOKEN:
    print("ERROR: DISCORD_TOKEN is missing!")
else:
    bot.run(TOKEN)
