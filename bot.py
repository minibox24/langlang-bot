import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import MaxConcurrency
from enum import Enum
from time import time
import aiohttp

from typing import List


class Languages(Enum):
    BASH = "bash"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    GO = "go"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    KOTLIN = "kotlin"
    PYTHON = "python"
    TEXT = "text"
    TYPESCRIPT = "typescript"

    @classmethod
    def get(cls, query: str, keyword: list = None):
        if keyword is None:
            keyword = [
                (Languages.BASH, ("bash")),
                (Languages.C, ("c")),
                (Languages.CPP, ("cpp")),
                (Languages.CSHARP, ("csharp", "cs")),
                (Languages.GO, ("go")),
                (Languages.JAVA, ("java")),
                (Languages.JAVASCRIPT, ("javascript", "js")),
                (Languages.KOTLIN, ("kotlin", "kt")),
                (Languages.PYTHON, ("python", "py")),
                (Languages.TEXT, ("text", "txt")),
                (Languages.TYPESCRIPT, ("typescript", "ts")),
            ]

        for lang, names in keyword:
            if query in names:
                return lang


class Status(Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    MEMORY_OVERFLOW = "memory_overflow"
    COMPILE_ERROR = "compile_error"


class LangLang:
    def __init__(self, url: str):
        self.url = url
        self.session = None

    async def eval(self, language: Languages, code: str, inputs: List[str] = []):
        if self.session is None:
            self.session = aiohttp.ClientSession()

        async with self.session.post(
            self.url,
            json={"language": language.value, "code": code, "inputs": inputs},
        ) as resp:
            data = await resp.json()

        return list(map(lambda r: (Status(r["status"]), r["result"]), data["results"]))


def setup_concurrency(text, delete_after: int = 5):
    old_acquire = MaxConcurrency.acquire

    async def acquire(self, message: discord.Message) -> None:
        key = self.get_key(message)

        if self.wait:
            if sem := self._mapping.get(key):
                if sem.value == 0:
                    await message.reply(
                        text.format(tasks=len(sem._waiters)), delete_after=delete_after
                    )

        await old_acquire(self, message)

    MaxConcurrency.acquire = acquire


bot = commands.Bot(command_prefix="!")
bot.langlang = LangLang("http://localhost:5000/langlang/eval")
bot.processes = {}


setup_concurrency("잠시만 기다려주세요. (대기: {tasks}개)")


@bot.event
async def on_ready():
    print("ready")


@bot.command("languages")
async def languages(ctx):
    await ctx.send(", ".join(map(lambda l: l.value, Languages)))


@bot.command("eval")
@commands.max_concurrency(10, commands.BucketType.default, wait=True)
async def _eval(ctx, *, code: str):
    if t := bot.processes.get(ctx.author.id):
        if time() - t > 190:
            del bot.processes[ctx.author.id]
        else:
            return await ctx.send("이미 다른 코드를 실행 중입니다.")

    bot.processes[ctx.author.id] = time()

    try:
        markdown = code.strip("```")
        lang = Languages.get(markdown.split("\n", 1)[0])
        code = markdown.split("\n", 1)[1]

        if lang is None:
            return await ctx.reply("Unknown language")

        message = await ctx.reply(
            embed=discord.Embed(title="컴파일 중..", color=discord.Color.blurple())
        )

        results = await bot.langlang.eval(lang, code)
        status, result = results[0]

        embed = discord.Embed(title="결과")
        embed.set_footer(text=lang.value)

        if status == Status.OK:
            embed.color = discord.Color.green()
            embed.description = result
        else:
            embed.color = discord.Color.red()

            if status == Status.ERROR:
                embed.description = result
            elif status == Status.COMPILE_ERROR:
                embed.description = result
                embed.color = discord.Color.orange()
            elif status == Status.TIMEOUT:
                embed.description = "시간 초과"
            elif status == Status.MEMORY_OVERFLOW:
                embed.description = "메모리 초과"

        if embed.description:
            embed.description = discord.utils.escape_markdown(embed.description)
            if len(embed.description) > 2000:
                embed.description = embed.description[:2000] + "..."

        await message.edit(embed=embed)
    finally:
        del bot.processes[ctx.author.id]


bot.run("TOKEN")
