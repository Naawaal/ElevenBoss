---
name: user-perspective-check
description: Validates a just-implemented feature by walking through it as the actual end user, not just as the developer who wrote it. Use after implementing or modifying any user-facing feature, Discord command, event handler, or endpoint, before considering it complete.
---

# User-Perspective Validation

Passing your own review answers "does this do what I told it to do." This
skill answers a different question: "does this actually hold up for someone
who didn't write it, doesn't know the internals, and isn't being careful."
Most bugs that survive normal review only surface when you trace the literal
sequence of user actions instead of the logic.

Run this **after** implementation, in addition to normal testing — not
instead of it. Do it before telling the user the feature is done.

## When to use this skill
- A new or modified Discord slash command, button, or modal
- A new or modified event handler that responds to user action
- A new or modified endpoint or service method a user-facing flow depends on

## How to use it

1. **Name the actual person, concretely.** Not "the user" — e.g. "a manager
   running `/train` on mobile with a weak connection," "a player who caught
   this same Pokémon five minutes ago," "the opposing manager affected by
   an action they didn't trigger," "a bot-controlled club with no human
   behind it." Different personas see different data and have different
   permissions — check the feature against each one that touches it.

2. **Walk the literal input path.** What do they type or tap, in what order,
   with what timing? Write the actual command/button/message, not a
   paraphrase of the logic.

3. **Assume the unhappy path first, not last.**
   - Run it twice, or double-tap the button?
   - Fires during a lock (matchday, season transition, an in-progress
     transaction)?
   - Cancels or navigates away mid-action?
   - The required resource is zero, missing, or stale (expired thread, old
     embed still on screen)?
   - Fires from two devices/sessions at once?

4. **Check what they actually see, not what the function returns.** Does an
   exception surface as a clear message, a silent no-op, or a raw stack
   trace? Can they tell a real success apart from a silent failure?

5. **Check timing reality.** Discord interactions expire in ~3 seconds if
   not deferred; DB/network calls can take longer. Would this exact user
   see "This interaction failed" through no fault of their own?

6. **Trace the payoff, not just the trigger.** If the action changes state,
   can the user verify that themselves (a follow-up command, an updated
   embed)? A user who can't observe the change assumes it silently failed
   and retries — which raises its own concurrency question to check.

7. If anything in 3–6 raises a real question, that's a gap. Go back to
   developer mode and fix it — don't reason your way into calling it fine.

## Output

Before considering the feature complete, write a short **User Perspective
Findings** note: persona(s) traced, path traced, gaps found (if any), fix
applied or still needed.
