/**
 * opencode telemetry: three lifecycle events and the session's token usage.
 *
 * Only what is collected is sent. Prompts, tool calls and tool results are not
 * hooked at all -- not filtered downstream, simply never asked for -- so this
 * plugin spawns nothing on the hot path of a turn. Nothing is awaited and every
 * failure is swallowed, so telemetry can never interrupt or slow a session.
 *
 * Three things have no Claude Code equivalent and are solved here. opencode
 * keeps its messages in a database rather than a record on disk, so at the end
 * of every turn they are read back over the SDK and handed to the shared Python
 * for their token counts and cost; the messages themselves are never stored. A
 * command has no ${CLAUDE_PLUGIN_ROOT} to resolve the feedback executable with,
 * so `shell.env` hands the shell tool one. And an installed copy of this plugin
 * has nothing in ~/.config/opencode/command, so /fn-eval is registered from the
 * `config` hook rather than left as a file to link.
 */
import { readFileSync } from "node:fs"
import { spawn } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const AGENT = "opencode"

const HERE = dirname(fileURLToPath(import.meta.url))
const BIN = resolve(HERE, "../bin")
const FN_EVAL = resolve(HERE, "../command/fn-eval.md")
// The shared package ships inside the Claude Code plugin, because that
// installer copies only its own directory. Every other integration reads it
// from wherever this file sits -- a checkout, or an installed package.
const PACKAGE_ROOT = resolve(HERE, "../../claude-code")

// Lifecycle only. A compaction or an error says something about a session, but
// neither is one of the five things collected, so neither is recorded.
const RECORDED_EVENTS = new Set(["session.created", "session.deleted", "session.idle"])

const FRONTMATTER = /^---\n([\s\S]*?)\n---\n/

const sessionOf = (event) => event.properties?.sessionID ?? event.properties?.info?.id

const quietly =
  (hook) =>
  async (...args) => {
    try {
      await hook(...args)
    } catch {}
  }

const feed = (module, args, payload) => {
  const child = spawn("python3", ["-m", `agent_telemetry.${module}`, ...args], {
    stdio: ["pipe", "ignore", "ignore"],
    env: { ...process.env, PYTHONPATH: [PACKAGE_ROOT, process.env.PYTHONPATH].filter(Boolean).join(":") },
  })
  child.on("error", () => {})
  child.stdin.on("error", () => {})
  child.stdin.end(JSON.stringify(payload))
}

/** One markdown command file, as the command definition opencode expects. */
const commandFrom = (path) => {
  const file = readFileSync(path, "utf8")
  const frontmatter = file.match(FRONTMATTER)
  return {
    description: frontmatter?.[1].match(/^description:\s*(.+)$/m)?.[1],
    template: file.replace(FRONTMATTER, ""),
  }
}

export const AgentTelemetry = async ({ client, directory }) => {
  const record = (hook, payload) => feed("hook", [AGENT], { hook, directory, ...payload })

  // The messages are read for their token counts and cost and are not kept;
  // `agent_telemetry.messages` takes the numbers and discards the rest.
  const reportUsage = async (sessionID) => {
    if (!sessionID) return
    const messages = await client.session.messages({ path: { id: sessionID } })
    feed("messages", ["--session", sessionID], messages.data ?? [])
  }

  return {
    // Left alone if the user has defined an fn-eval of their own.
    config: quietly(async (config) => {
      config.command ??= {}
      config.command["fn-eval"] ??= commandFrom(FN_EVAL)
    }),

    event: quietly(async ({ event }) => {
      if (!RECORDED_EVENTS.has(event.type)) return
      record(event.type, { sessionID: sessionOf(event), ...event.properties })
      if (event.type === "session.idle") await reportUsage(sessionOf(event))
    }),

    "shell.env": quietly(async (_input, output) => {
      output.env.AGENT_TELEMETRY_BIN = BIN
    }),
  }
}
