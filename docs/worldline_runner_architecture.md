# BLACK Worldline Runner Architecture

Pipeline: official observation -> canonical truth -> board vision -> plan templates -> runner arena -> hostile-world judge -> persistent plan -> legal action index.

Core rules:
- Bind in-play Pokemon by `(playerIndex, serial)`, never by card ID alone.
- Separate physical Energy cards from effective Energy units.
- Generate coherent plans before scoring individual actions.
- Every candidate includes the opponent's best response and abort conditions.
- Judge lexicographically: immediate loss, terminal win, prize clock, hostile-world survival, irreversible resources, opponent pain, regret.
- Pending plans persist across select contexts and abort on transition-contract failure.
- Official CABT observation and Search API transitions are the runtime authority.

Dragapult and Rocket Mewtwo use separate standalone branches and entrypoints on top of this shared kernel.