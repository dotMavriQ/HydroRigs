<img src="hydrorigs.png" alt="HydroRigs" width="180" align="right" />

# HydroRigs

HydroRigs is a small status and monitoring tool for people who want to maximize the utility of cheap, free-tier, and quota-limited AI tooling.

The point is simple: use the rigs you already have, use them hard, and stop wasting expensive requests because one provider quietly hit a limit before another one did.

The name is a nod to *Oblivion*, but the tool itself is practical. It exists so a frugal engineer can see every usable rig at a glance and route work to the cheapest viable option.

This is not a chatbot wrapper and it is not trying to be a universal agent framework. It does one job: keep track of the tools you actually use, tell you which ones are ready, tell you which ones are cooling down, and make that information cheap to surface in a status bar.

## What It Does

HydroRigs tracks supported CLI tools and provider-backed budgets, then reduces all of that into something you can glance at:

- which tools are ready right now
- which tools are on cooldown
- how long until a cooldown ends
- which budget-backed providers are healthy, low, or exhausted
- when a rig comes back online, so you can get a desktop notification and move on

The intended end state is simple: you keep working, the rigs keep harvesting, and the bar tells you when one of them is worth touching again.

More concretely, HydroRigs helps you:

- lean on free or cheaper models before touching premium ones
- avoid probing dead providers by hand
- shift work between tools based on real cooldowns and budget state
- keep every usable CLI in rotation instead of defaulting to the most expensive one

When the indicators line up, that is your signal to let the Hydrorigs brrrr again.

## Current Coverage

HydroRigs currently supports a mix of cooldown-style and budget-style monitoring:

- Claude
- Codex
- Gemini
- GitHub Copilot premium requests
- Aider with provider-backed balance checks

Some providers are proactively pollable. Others are event-driven and infer cooldowns from the real limit messages those tools emit. The project is built around whatever reliable signal is actually available, not whatever would look nicest in a table.

## Coverage Spreadsheet

| Provider | Status bar emoji | Plan / bucket being tracked | Monitor type | What HydroRigs actually watches | `🟢` means | `🟡` means | `🔴` means | Countdown means | Practical utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude | `🎭` | Claude Pro usage window | Cooldown | Real Claude limit/reset messages | Claude is usable right now | n/a | n/a | Claude is cooling down until the timer ends | You know exactly when you can get back to grinding instead of manually retrying |
| Codex | `📜` | ChatGPT Plus Codex allowance | Cooldown | Real Codex usage-limit messages | Codex is usable right now | n/a | n/a | Codex is blocked until the timer ends | You stop wasting time probing Codex when your Plus allowance is temporarily exhausted |
| Gemini | `♊` | Gemini 2.5 Pro free-tier quota | Budget | Real Gemini Code Assist quota state | Pro quota is comfortably available | Pro quota usage is high | Pro quota is exhausted | n/a | If Pro is red, you can fall back to Gemini’s cheaper or free models like Flash or Flash-Lite and keep moving |
| GitHub Copilot | `🐙` | Premium requests on paid Copilot plans | Exhaustion + reset | Real local Copilot quota exhaustion plus monthly reset timing | Premium-request bucket is still usable | n/a | n/a | Premium requests are exhausted until the reset | You know when to stop expecting premium models and drop to included models such as `GPT-5 mini`, `GPT-4.1`, or `GPT-4o` |
| Aider | `🩹` | DeepSeek-backed spend / balance | Budget | Real DeepSeek account balance | Balance is healthy | Balance is below `$10` | Balance is below `$0.50` | n/a | You can keep Aider on the cheap path until it starts running low, then top up or switch providers before it dies |

Notes:

- Gemini is especially useful here because it has genuinely usable free or cheaper models, so the Pro indicator tells you when to stop spending effort on the premium bucket and just let the cheaper rigs work.
- GitHub Copilot matters because premium requests are not the same thing as basic usability. Even when premium requests are gone, included models can still keep the rig productive.
- Claude and Codex are cooldown-style rigs: when the timer disappears and goes green, that is when you let the Hydrorigs brrrr again.

## Waybar / WM Use

The original use case is a Waybar module on a tiling window manager, with optional `dunst` notifications when a rig comes back online.

A typical compact output looks like this:

```text
🎭: 2d 18h | 📜: 🟢 | ♊: 🔴 | 🐙: 2w | 🩹: 🟢
```

That gives you the whole situation in one line:

- cooldowns when a tool is blocked
- a green light when it is ready
- warning and critical states for budget-based providers

## Why This Exists

If you are paying attention to limits, you already know the problem:

- one tool is hard-capped for the day
- another has a rolling cooldown
- another still works, but only on the cheap model
- one provider has money left, another is nearly empty
- the only way to learn any of this is to poke each CLI and waste time

That is dumb operationally. HydroRigs exists to make those constraints visible before they waste your attention.

For the cost-conscious engineer, that matters. The point is not to look impressive. The point is to squeeze every useful cycle out of the rigs you already have, route work intelligently, and avoid burning premium requests when a cheaper path is still available.

That is the actual thesis of the tool: maximize utility, minimize waste.

It is also what makes the status line valuable. The point is not just to show that a rig is blocked. The point is to show when you should switch down to free Gemini models, fall back to included Copilot models like GPT-5 mini, or wait for Claude or Codex to come back online before you spend money or premium requests unnecessarily.

## Installation

Clone the repo and run:

```bash
./install.sh
```

That installs the CLI entrypoint and the user service. From there you can wire it into your status bar, poll it on demand, or run the daemon for background sync and notifications.

## Commands

HydroRigs is centered around a few straightforward commands:

- `hydrorigs status`
- `hydrorigs sync`
- `hydrorigs daemon`
- `hydrorigs wrap ...`

The important one for most people is `status`. That is the line you feed into Waybar.

## Final Word

AI tooling is not frictionless. HydroRigs is for seeing the limits clearly and getting the maximum amount of useful work out of the cheapest viable path anyway.

References:

- GitHub Copilot requests and included models: https://docs.github.com/copilot/concepts/copilot-billing/understanding-and-managing-requests-in-copilot
- GitHub supported model multipliers: https://docs.github.com/en/copilot/reference/ai-models/supported-models
- Gemini free-tier rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
