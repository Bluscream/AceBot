# ![Avatar](https://i.imgur.com/Sv7L0a1.png) A.C.E. - Autonomous Command Executor

[![Discord Bots](https://top.gg/api/widget/status/367977994486022146.svg)](https://discordbots.org/bot/367977994486022146)
[![Discord Bots](https://top.gg/api/widget/servers/367977994486022146.svg)](https://discordbots.org/bot/367977994486022146)

A fun, general purpose Discord bot!

[Click here to add it to your server!](https://discordapp.com/oauth2/authorize?&client_id=367977994486022146&scope=bot&permissions=268823632)

The bot was initially made for the
[AutoHotkey server](https://discord.gg/tPGdSr2).

Support server invite [here.](https://discord.gg/X7abzRe)

## Table of Contents

- [Usage](#usage)
  - [General commands](#general-commands)
  - [Starboard](#starboard)
  - [Tags](#tags)
  - [Bot configuration](#bot-configuration)
  - [Moderation](#moderation)
  - [Welcome](#welcome)
  - [Roles](#roles)
  - [Feedback](#feedback)
- [Installing the bot](#installing-the-bot)
- [Acknowledgements](#acknowledgements)

## Usage

### General commands

The bot has a plethora of commands. To invoke these, send a message starting with `.` followed by the command name.
For example, `.woof` would invoke the `woof` command.

The `help` command can be ran at any point for reference how to use the bot. If you need help about a specific command,
`help *command name here*` can be run.

```
remindme    Have the bot remind you about something in the future
wolfram     Query Wolfram Alpha
weather     Get the weather at a location
choose      Pick an item from a list of choices
hl          Highlight some code
info        Information about a member
server      Information about the server
fact        Get a random fact
8           Classic 8ball!
And many more!
```

It can fetch cute random images on demand!

```
woof        Get a random doggo picture
meow        Get a random cat picture
floof       Get a random fox picture
quack       Get a random duck picture
```

### Starboard

Classic Starboard implementation.

A starboard is a channel where "starred" messages are posted. A message can be starred by anyone by reacting to it with
the :star: emoji. At this point anyone can additionally star the message, giving it more stars.

To create a starboard use the `starboard create` command. This will create a channel where starred messages will be posted.

Automatic starboard cleaning can be enabled using `starboard threshold`. To have starred messages with fewer than 5 stars be
removed after a week, do `starboard threshold 5`.
To disable auto-cleaning, do `starboard threshold`. The starboard can also be
temporarily disabled (to clean it, for example) using `starboard lock` and enabled using `starboard unlock`.

Other misc. starboard commands:

```
star            Star a message by ID
unstar          Unstar a message by ID
star info       Show information about a starred message
star show       Bring up a starred message in the current channel
star delete     Delete a starred message from the starboard. Appropriate permissions/relations required to run this.
```

Run `help starboard` for a complete list.

### Tags

The tag system is immensely useful for bringing up text or images on demand.

To try it out, you can create a new tag interactively by simply running `tag make`.

Here's an example of the tag system in work:

# ![Tag demonstration](https://i.imgur.com/LxEteHI.gif)

A few of the tag commands:

```
tag             Bring up a tag
tag create      Create a new tag
tag make        Create a new tag interactively (recommended!)
tag edit        Edit one of your tags
tag delete      Delete one of your tags
tag list        List a members tags, or all the server tags
tag info        Extensive information about a tag
tags            List all of your own tags
```

Run `help tag` for a complete list.

### Bot configuration

The prefix of the bot is configurable using the `prefix` command. If you forget the current prefix, the help menu can be brought up by simply mentioning the bot.

```
.prefix !
# new commands are now invoked using !
!woof
```

A role can be set that can also configure the bot using the `modrole` command.
Members with the mod role can delete any tag, delete starred messages, change the prefix, etc. Only thing members with this role can't do is change the mod role, as this requires administrator privileges.

```
.modrole @somerole
```

To see what the current configuration is, run `config`.

### Moderation

To enable member muting, create a role that prohibits sending messages and set it with `muterole <role>`.
To mute a member do `mute <member>` and to unmute use `unmute <member>`. Similarly, `ban` and `unban` also exist.

You can issue tempbans and tempmutes:

```
tempban <member> <amount> <unit> [reason]
tempmute <member> <amount> <unit> [reason]

examples:
tempban @dave 5 days Stop spamming!
tempmute @bobby 1 hr Read rules again.
```

Tempbanning will make the bot attempt to send a DM to the banned member with the reasoning for the ban, if provided.

### Welcome

The bot can be configured to send a message each time a new member joins your server.

To set this up, first specify a channel the messages should be sent in using `welcome channel`. Then set up a welcome message using `welcome message`. A list of replacements is listed here:

```
{user}          Replaced with a mention of the member that joined
{guild}         Replaced with the server name
{member_count}  Replaced with the server member count
```

To see that the welcome system works you can run `welcome test`. If it fails it will tell you what to fix!

Run `help welcome` for a complete list of commands.

### Roles

The bot can create a role selector for you. Here's an example of such a selector:

# ![Role selector](https://i.imgur.com/1RoSHLs.png)

By clicking the reactions the user is given the correlated role.

Run `help roles` for a full list of commands.

### Feedback

You can send thoughts, feedback and suggestions directly to me by using the `feedback` command!

## Installing the bot

**If you want this bot in your server, I would prefer if you invite the official instance using the
[invite link](https://discordapp.com/oauth2/authorize?&client_id=367977994486022146&scope=bot&permissions=268823632).**

Nevertheless, if you want to set it up for yourself, follow the instuctions in [`INSTALL.md`](INSTALL.md).

## Acknowledgements

Contributors: CloakerSmoker, GeekDude, sjc, Cap'n Odin
