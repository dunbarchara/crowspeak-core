# crowspeak_engine: design and rationale

This records how the engine foundation is shaped and why. It covers the restructure of the flat prototype scripts into the `crowspeak_engine` package (task: "Restructure flat scripts into a crowspeak_engine package with an Engine boundary"). For the product-level picture, see `docs/crowspeak_architecture_strategy.md` in the workspace root.

## 1. Goal

Clients (the reference CLI now, the R3F 3D frontend later via the gateway) should be **thin consumers**. The engine takes user input and yields events. It never prints, never calls `input()`, and never reads the environment.

Before the restructure, `chat.py` owned everything: env config at import time, the LLM call, terminal prompts, the loop, and error rollback. Nothing could be reused by a second client.

## 2. Guiding principles

1. **Flexible by default, rigid by opt-in.** Learners should engage however they like and change settings whenever they like. Rules like "this NPC speaks no English" are real features, but they are explicit constraint fields, never built-in assumptions. A constraint field is nullable and defaults to unrestricted.
2. **Text is first-class; voice is layered on top.** The text path (`send_text`) is a complete path, not a fallback. Voice will add `send_audio` in front of the same pipeline and emit the same events.
3. **Events are domain events, not view models.** Clients decide how to render them. The same stream must serve a terminal and a WebGL client without engine changes.
4. **Build the seams, not the systems.** Where we know the future shape (multiple NPCs, Groups, voice), we leave a seam. We don't build the machinery yet.

## 3. Domain model

```
Engine ──creates──> Session            world-level, one per load-in
                      ├─ learner: Learner          (LanguageProfile + id)
                      ├─ prefs: InteractionPrefs   (session defaults)
                      └─ conversations: {npc_id -> Conversation}

Conversation                            learner <-> one Npc
                      ├─ npc: Npc                  (persona + LanguageProfile + constraints)
                      ├─ prefs: InteractionPrefs   (per-conversation override)
                      └─ history: list[Message]    (per-Npc; resumes if you return)
```

### Glossary

Use these terms consistently in code, docs and tasks.

| Term | Meaning |
|---|---|
| **Learner** | The human practicing a language, as a party in a session: a `LanguageProfile` plus an id. The engine has no accounts, so it never says "user". |
| **User** | An account in a wrapper app (login, billing, a `users` table). Not an engine concept. A user maps to a Learner at the app boundary. |
| **NPC** | The character the learner talks to: persona, `LanguageProfile`, optional constraints. |
| **Speaker** | Only the generic "whoever is talking", as in `speaker_id` (an NPC id, or `"user"` for now; it will become the learner id, see the Macro task "Use learner id as speaker_id"). It never means the NPC or the NPC's LLM. |
| **NPC reply** | The conversational LLM call that plays the NPC and streams its answer. Replaces the earlier "speaker" wording. |
| **Analyzer** | A separate, structured-JSON LLM call that reviews the learner's input and runs beside the NPC reply (corrections now; vocab tracking and others later). It never speaks to the learner as a character. |
| **Role** | `system` / `user` / `assistant` on `Message`: the OpenAI-protocol field, which keeps its wire names. `user` means the learner's messages there. It never names an LLM assignment; that is a **Job**. |
| **Provider** | A backend adapter: vendor or endpoint, credentials and client (`AzureOpenAIProvider`, `LocalOpenAIProvider`). Implements `LLMProvider`, and optionally `JSONProvider`. See section 8. |
| **Job** | The named piece of work a provider is assigned: `npc`, an analyzer's or generator's name (`corrections`, later `vocab`, `daily_tasks`), or any string a consumer defines. A job resolves to a provider through the registry, falling back to the default. |
| **Model** | The deployment or model name inside a provider (an Azure deployment, an Ollama tag). Not a registry layer: it is a provider constructor argument, so two models are two provider instances. |
| **Session / Conversation** | World-level state for one learner, and one learner-NPC pairing with its history (see below). |

### Why Session is world-level and does not live inside Conversation

The original design had a `Conversation` owning a `Session`. That fits a single chat, but not the sandbox we are building toward. There, the user loads in once with their language config and then walks up to many NPCs, each with their own persona, level and history, while the learner's config stays the same throughout. So:

- **Session** holds what is true for the whole play-through: the learner and default preferences.
- **Conversation** holds what is true for one learner-NPC pairing: the NPC and the history. `session.converse(npc)` is get-or-create by `npc.id`, so walking away and coming back resumes the same conversation.

The old `session.py` mixed both lifetimes, since it held both the user's config and one chat's history. That was the flaw this split fixes.

### `LanguageProfile`: one shape for learner and NPC

```python
LanguageProfile(native: str, target: str | None, proficiency: Proficiency | None)
```

The learner and every NPC use the same shape. A `target` requires a `proficiency`, and `target` must differ from `native`. A learner additionally must have a target (checked in `Learner`). An NPC may have none (a native speaker) or one (a non-native).

This is what makes scenarios like "a non-native, beginner NPC the learner has to catch mistakes from" expressible with no special cases. The plumbing is generic, and only the prompt content for deliberate mistakes is missing (see section 9).

## 4. Interaction preferences

`InteractionPrefs(learner_input_language, npc_response_language)` are free-form language codes. **Any combination is valid**: English in and Japanese out, Japanese in and English out, the same language both ways, or a third language. Learners switch modes for real reasons: practicing listening means responses in the target language, while practicing speaking may mean responses in the native language, to confirm they were understood.

Resolution runs most specific first: **conversation, then session, then natural default**. Preferences are mutable mid-session (`Session.set_prefs`, `Conversation.set_prefs`).

Natural defaults:
- Input: the learner's native language (their target if the NPC doesn't understand the native one).
- Response: the learner's target language if the NPC knows it. Otherwise the NPC's native language.

The engine does **not** check preferences against the parties' languages by default. The original code did (both had to be the native or target language), and we removed it deliberately.

## 5. Constraints as opt-in features

An `Npc` may set `understands` and/or `speaks` (a `frozenset` of language codes). `None`, the default, means unrestricted. When set, they apply in two places:

- **Config time:** creating a conversation or calling `set_prefs` raises `ConstraintError` if the resolved input or response language is outside the set. A client can surface that error in its UI. `Session.set_prefs` is atomic: if any existing conversation can't accommodate the new defaults, nothing changes.
- **Prompt time:** the NPC is told what it can't understand or speak, so it responds in character.

The natural defaults respect constraints. An NPC that only understands Japanese works out of the box, and the learner is simply expected to speak Japanese. Only an explicit preference that contradicts the constraint raises. This gives the "no English at all" NPC as a normal feature without making it a rule of the system.

## 6. Personas as a first-class feature

`Npc` carries `id`, `name`, `persona` (free text), `language`, and the optional constraints. Specifying personas is meant to be a core capability of the engine, but the barrier to entry stays minimal: `session.converse()` with no NPC gives a generic partner (`Npc.default`) who natively speaks the learner's target language. Two lines gets you talking.

The prompt is composed in `prompts.py`. **The persona says who the NPC is; the language profiles say how they speak.** A persona is the first line of the prompt, and the language rules follow it, so a persona can't remove the language calibration. A conduct rule follows too: converse naturally, never teach or correct unless asked directly, and reply in plain text (no markdown). The NPC is never cast as a teacher, because feedback on the learner's language comes from analyzers (section 7), not from the character.

Calibration (`proficiency_adapters.get_adapter`, unchanged) is applied depending on who is speaking what:
- NPC speaking its own non-native target: calibrate to the **NPC's** level, so a beginner NPC talks like a beginner.
- NPC speaking the learner's target: calibrate to the **learner's** level (the accommodating partner, as before).
- Replying in a language that is neither (e.g. the learner's native language): no calibration.

## 7. Events and the turn loop

```python
async for event in conversation.send_text("こんにちは"):
    ...
```

| Event | Meaning |
|---|---|
| `TranscriptDelta(text, role, final)` | A streamed piece of the reply. One extra event with `final=True` closes the stream. |
| `ExpressionChange(label)` | Only with the `expression` feature on. How the NPC is delivering what follows. Always precedes the turn's first text (`neutral` if the model emitted no tag); may recur mid-reply. |
| `TurnCompleted(message)` | The full assistant message, after it has been added to history. |
| `CorrectionsReady(message_id, corrections)` | Only with the `corrections` feature on (designed, task 4b). Feedback on the learner's message `message_id`, after `TurnCompleted`. |
| `AnalyzerError(analyzer, message_id, message)` | An analyzer failed. Non-fatal: the conversation is unaffected. Distinct from `EngineError` so wrappers can tell them apart. |
| `EngineError(message, recoverable)` | The provider failed. The pending user message was rolled back, so the conversation stays usable. |
| `SessionStarted(learner_id)` | Built by `session.start_event()`. It is not yielded by a turn, so a gateway can send it when a client connects. |

Conversation events carry `session_id`, `conversation_id` and `speaker_id` (the NPC id, or `"user"`), so one client can multiplex many conversations in a single session. That is the concrete payoff of the Session/Conversation split.

If a consumer stops consuming `send_text` mid-stream (task cancelled, client disconnects), `finally` cleanup keeps history coherent: the partial reply is kept as a `Message(..., interrupted=True)` if any chunks arrived, or the pending user message is rolled back if none did. No event is yielded for this — the disconnected consumer isn't listening — it only matters to a later reader of `history` (e.g. resuming a session, or the future gateway).

**NPC output and expression tags (opt-in feature).** With `Features(expression=True)` the NPC replies in plain streamed text with inline tags from a closed vocabulary (`EXPRESSIONS`: neutral, happy, sad, angry, surprised, thinking), e.g. `[happy] ¡Hola! [thinking] ¿Y tú?`. `ExpressionTagParser` (`expression.py`) strips them incrementally (a tag may split across deltas) and the conversation turns them into `ExpressionChange` events, so clients and TTS adapters only ever see clean text. With the feature off (the default) the prompt has no tag instruction, no `ExpressionChange` is emitted, stray tags are still stripped, and the model is sent clean history. Unknown word-like tags are dropped and logged; other bracketed text is kept. `Message.content` is the clean text and `Message.raw` the tagged text, which is what is sent back to the LLM so it keeps following the format. This applies to the NPC's reply only: other LLM calls (corrections, teaching) use structured JSON. Alternatives not chosen, kept as pivot options: JSON schema with the expression before the text; function calling such as `set_expression(label)`; post-hoc metadata events; native TTS cue passthrough (a variant done in the TTS adapter); neutral voice with animation-only emotion. See the Macro task "Add structured NPC output".

**Features.** `Features` (`features.py`) holds opt-in capabilities and layers like `InteractionPrefs`: a session default (`start_session(..., features=)`, `set_features`) and a per-conversation override (`converse(..., features=)`, `Conversation.set_features`); `None` falls through, and the unset default is off. Flags are read at the start of each turn, so a change applies from the next turn. This is done in the engine (not by clients ignoring events) so a disabled feature costs no prompt tokens and no events. Voice will join as another field, but also needs STT/TTS adapters registered on the `Engine`; enabling it without one should fail fast. See the Macro task "Add engine feature toggles model".

**Corrections analyzer (designed, task 4b; not yet implemented).** The NPC never critiques, so feedback on the learner's own input comes from a separate analyzer LLM call that returns structured JSON. Decisions:

- **Scope.** Learner turns only; the NPC is not corrected. It runs only when `Features.corrections` is on (default off) and the resolved input language is the learner's target language. Analyzer input is `(speaker, text)`, where the speaker is the learner or an NPC, so a future "spot the NPC's mistakes" analyzer is not blocked.
- **Parallel, off the critical path.** The call starts when the learner's message is added and runs alongside the reply. After `TurnCompleted`, the turn stream yields `CorrectionsReady` or `AnalyzerError` and then ends. If the consumer disconnects, the analysis still finishes and is attached to history; it is cancelled if the turn is rolled back after a speaker error.
- **Input.** The learner message plus the last 2-4 turns of history, each marked NPC or LEARNER, the target and native language (region codes such as `es-MX`) and the CEFR level. No persona. It analyzes the clean `Message.content`, and for voice that will be the transcript.
- **Output.** `Corrections(language, original, corrected, is_correct, items, praise?)`. Each item has `original` (a quoted substring), `suggestion`, `span`, `category`, `severity`, `explanation`, `explanation_language` and an optional `confidence`. Categories are a closed set (grammar, vocabulary, spelling, naturalness, punctuation); severity is `error` or `suggestion`. The model returns the quoted substring and the engine computes `span`, because models count offsets badly. Explanations default to the learner's native language.
- **Level-aware.** Fewer, gentler flags at A1-A2, with a cap on items. Valid regional variants (for example Mexican *ustedes*, *carro*, *platicar*) must not be flagged. Spelling and punctuation apply to text only; pronunciation needs audio and is a separate future analyzer.
- **History.** The result is stored on the learner's `Message.corrections` (`None` means not analyzed, an empty result means nothing found), in memory only. Prompt building ignores it, so the NPC never sees the grading. Database persistence comes later.
- **Failure.** Bad JSON or a provider error becomes a non-fatal `AnalyzerError` and never affects the conversation.
- **Providers.** Corrections is its own **Job** (`corrections`), so its provider is configurable independently of the NPC's (accuracy matters more than speed here). It needs the JSON-schema capability (`JSONProvider.complete_json`), which the registry checks per job (section 8).

`AgentAudioChunk` from the architecture doc is deliberately not defined yet, since the doc doesn't specify its schema and we'd be inventing it. `GrammarFeedback` is superseded by `Corrections` above.

**Async and streaming from the start.** The target pipeline is async STT to LLM to TTS, and streaming deltas are what the doc's `TranscriptDelta` implies. Adding these later would change every caller.

## 8. Boundaries

- **`LLMProvider`** (`llm/base.py`) is a small protocol: `stream(messages) -> AsyncIterator[str]`. The engine depends on that and nothing else. `AzureOpenAIProvider` is the first adapter and takes its configuration in its constructor; the adapters read no environment variables themselves. `LocalOpenAIProvider` (`llm/local.py`) targets any OpenAI-compatible local server such as Ollama. `llm/factory.py` builds either from a `ProviderConfig`, or from `LLM_*` environment variables as a convenience (callers are responsible for loading `.env`). Nothing is read at import time, so `import crowspeak_engine` never fails for lack of credentials. Both adapters share one streaming loop in `llm/_openai_stream.py`.
- **No terminal I/O, no environment reads in the engine.** `tests/test_boundary.py` enforces this. The only exception is `llm/factory.py`.
- **The CLI is separate** (`crowspeak_cli`): the prompts, printing, UTF-8 stdout fix for Windows, and `--persona` flag all live there. It is deliberately minimal, because it is a reference client.

### Providers, Jobs and Models

Status: **the registry and the config layer (including the env mapper) are implemented**; CLI support for per-job providers and generators are still planned (Macro epic "Foundations: per-job LLM providers and installable engine package"). The CLI still builds one provider with `provider_from_env()`.

**Why.** Different LLM work wants different backends: a larger model for corrections, a cheap or local one for the NPC, and a consumer's own for jobs the engine doesn't know (for example generating a day's task scenarios). Each may point at a different endpoint or key per environment.

**Terms.** A **Provider** is a backend adapter, a **Job** is the named work it is assigned, and a **Model** is the deployment inside a provider (glossary, section 3). One provider instance can fill several jobs, and one job can be re-pointed at another provider without touching the engine.

**Jobs are plain strings, one per name.** `npc` for the NPC reply, an analyzer's `name` (`corrections`), a generator's name. There is no fixed category enum, so a consumer adds a job by using a new name. The built-in constants are `npc` and `corrections`.

**Registry.** `Providers(default, jobs={})` (`llm/providers.py`) is the single place that answers "which provider runs this job":

- `for_job(name, needs="stream" | "json")` returns `jobs[name]` if set, else `default`. If the result lacks the needed capability (`stream()` or `complete_json()`) it raises `ProviderError`, a `ValueError`, naming the job, the capability and the provider. This replaced the ad hoc `hasattr(..., "complete_json")` check in `Conversation._corrections_analyzer()`.
- `jobs` is copied and read-only, so changing the caller's dict afterwards doesn't change the registry.
- Resolution is most specific first (job, then default), the same layering as `InteractionPrefs` and `Features`.
- `Engine(providers=...)` is the full form. `Engine(llm, analyzer_llm=x)` stays as sugar for `Providers(default=llm, jobs={"corrections": x})`; giving both forms, or neither, is a `ValueError`.
- The NPC provider is resolved when a conversation is created (`converse()`), so a provider that can't stream fails there rather than mid-turn. Analyzer providers are resolved per turn, because `Features` can change between turns.
- An analyzer's `name` is its job name (`CorrectionsAnalyzer.name == JOB_CORRECTIONS`).

**Configuration is explicit first; env is a convenience.** A wrapper app owns where its config comes from (settings, a secrets store) and passes values in, so there are three levels, all ending in the same `Providers`:

1. **Adapters.** Construct `AzureOpenAIProvider(...)` / `LocalOpenAIProvider(...)` directly and pass `Providers(default=..., jobs=...)`. Nothing else is needed.
2. **Declarative config.** `ProviderConfig(kind, model, endpoint, api_key, api_version)` describes one provider; `build_provider(config)` builds it and `providers_from_config(default, jobs)` builds a registry. This reads no environment, supports a different endpoint or key per job, and keeps `api_key` out of `repr`.
3. **Environment mapper** (`llm/factory.py`, the only code in the engine that reads env), for the CLI, tests and local development:
   - `LLM_PROVIDER` selects the default provider (`azure` if unset). `provider_from_env()` is the single-provider shorthand.
   - `providers_from_env(jobs=("npc", "corrections"))` reads `LLM_<JOB>_PROVIDER` and `LLM_<JOB>_MODEL` for each job it is given (job upper-cased, non-alphanumerics replaced by `_`, for example `LLM_CORRECTIONS_PROVIDER=azure`). A provider-only override builds that kind with its own model variable; a model-only override builds the default's kind with that model. A job with neither falls back to the default.
   - Jobs are named by the caller, not discovered, so a consumer-defined job is passed in `jobs=`.
   - Endpoint and key stay provider-level (`AZURE_OPENAI_*`, `LOCAL_LLM_*`) and shared by every job on that provider. A job that needs its own account uses level 2.
   - Blank values count as unset. An unknown provider kind, or a missing Azure variable, raises `ValueError` naming the variable.
   - This makes the useful mixed setup expressible from env: a local NPC (`LLM_PROVIDER=local`) with corrections on Azure (`LLM_CORRECTIONS_PROVIDER=azure`). It stays subject to the testing policy: live Azure calls need explicit confirmation.

**Voice and translation (names reserved, nothing built).** `stt` and `tts` are jobs, but they are filled by their own protocols (`SpeechToText`, `TextToSpeech`), not `LLMProvider`. Those protocols are defined when the voice work starts, and enabling the voice feature without a provider for them fails fast (section 7). `translation` is an ordinary LLM job unless a non-LLM backend (a translation API) appears, in which case it gets its own protocol the same way.

**Non-conversation jobs.** Analyzers are turn-shaped (`AnalyzerContext`). Work that has no conversation, such as daily task scenarios, is a *generator* with its own job name that runs through the same registry. Its protocol is a separate task in the epic. Scheduling, caching and persistence of generated content belong to the wrapper app, not core.

## 9. Package layout

```
src/crowspeak_engine/
  engine.py       Engine(llm | providers=).start_session(learner, prefs=None)
  session.py      Session, Learner
  conversation.py Conversation: history, turn loop, rollback
  npc.py          Npc, Npc.default
  profile.py      LanguageProfile
  prefs.py        InteractionPrefs, resolve_prefs
  prompts.py      system-prompt composition
  events.py       domain events
  llm/            LLMProvider protocol, Azure + local adapters, env factory
                  providers.py: Providers, the Job registry
  proficiency*.py CEFR levels and per-language adapters (moved unchanged)
src/crowspeak_cli/  reference terminal client
tests/
```

Package naming: import `crowspeak_engine`, PyPI `crowspeak-engine`, CLI `crowspeak-cli`. `crowspeak-core` remains the **repo** name only, since the repo contains the engine, gateway, CLI and protocol schemas. Naming the package after the repo would blur that boundary and force a rename when the gateway arrives.

## 10. Alternatives we rejected

| Rejected | Why |
|---|---|
| Conversation owns Session | Wrong for a sandbox with many NPCs and one learner config. See section 3. |
| Validate prefs against native/target languages | Blocks legitimate modes (third languages, any input/response mix). Constraints belong on the NPC, opt-in. |
| Sync, non-streaming first pass | The end state is async and streaming, so it would mean rewriting every caller. |
| Keep a `chat.py` shim | The CLI should be minimal enough that a shim is redundant. |
| Build Group / multi-NPC routing now | Session already sits above conversations, so nothing needs to change when they arrive. |
| Define all events in the architecture doc | Their schemas aren't specified yet. |
| Call the assignments "roles" | `Role` already means `system`/`user`/`assistant` on `Message`. We use **Job**. |
| Call them "slots", "tasks" or "domains" | "Slot" doesn't convey what the LLM is doing. "Task" collides with the R3F daily tasks. "Domain" is overloaded (domain model) and names the subject area, not the function. |
| A fixed set of job categories (`npc`, `analysis`, `generation`) | One shared `analysis` job would stop a corrections analyzer using a bigger model than a later vocab analyzer. Jobs are plain strings, one per analyzer or generator name. |
| Env vars as the primary configuration surface | A library shouldn't make its behaviour depend on ambient process state, and a wrapper pulls secrets from its own store. Configuration is explicit (adapters, `ProviderConfig`), and env is a mapper onto it in the factory. |

## 11. Known gaps and next steps

These are intentionally open and are the first things to discuss after this foundation:

- **Deliberate mistakes.** The "spot the beginner NPC's mistakes" game needs a behavior or role field on `Npc`, and probably a `GrammarFeedback` event. Today's adapters say "simplify", and realistic errors are new prompt content.
- **Voice.** `send_audio`, plus `AgentAudioChunk` and VAD/STT/TTS orchestration.
- **Corrections.** Designed (see section 7) but not yet implemented (task 4b). The Phase 1 latency target (under 1s) also needs measuring.
- **History growth.** History is replayed in full each turn, with no truncation or token budgeting.
- **Persistence.** Sessions and conversations are in-memory only.
- **Gateway and protocol.** A wire format for events (WebSocket) and a place for `SessionStarted` to be sent.
- **Multi-provider job routing.** The `Providers` registry and per-job configuration (`ProviderConfig`, `providers_from_env`) are implemented (section 8, "Providers, Jobs and Models"). Still open: a CLI that builds and shows the provider and model per job.
- **Non-conversation structured jobs (generators).** A protocol and `engine.generate()` for work with no conversation, such as generating a day's task scenarios scaled to the learner's proficiency. Tracked in the same epic.
