/**
 * opencode telemetry: every hook worth recording, piped to the shared package.
 *
 * The payloads go out as JSON on the stdin of the same Python that backs the
 * Claude Code plugin, where the opencode adapter maps them onto the shared
 * taxonomy. Nothing is awaited on the hot path and every failure is swallowed,
 * so telemetry can never interrupt or slow an opencode session.
 *
 * Two things have no Claude Code equivalent and are solved here. opencode has
 * no transcript file to point at -- its messages live in a database -- so at
 * the end of every turn they are read back over the SDK and dumped beside the
 * event log. And a command has no ${CLAUDE_PLUGIN_ROOT} to resolve the feedback
 * executable with, so `shell.env` hands the shell tool one.
 */
import { spawn } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const AGENT = "opencode"

const HERE = dirname(fileURLToPath(import.meta.url))
const BIN = resolve(HERE, "../bin")
// The shared package ships inside the Claude Code plugin, because that
// installer copies only its own directory. Every other integration reads it
// from the repository checkout, as here.
const PACKAGE_ROOT = resolve(HERE, "../../claude-code")

const RECORDED_EVENTS = new Set([
  "session.created",
  "session.deleted",
  "session.idle",
  "session.compacted",
  "session.error",
])

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

export const AgentTelemetry = async ({ client, directory }) => {
  const record = (hook, payload) => feed("hook", [AGENT], { hook, directory, ...payload })

  const dumpTranscript = async (sessionID) => {
    if (!sessionID) return
    const messages = await client.session.messages({ path: { id: sessionID } })
    feed("transcript", ["--session", sessionID], messages.data ?? [])
  }

  return {
    event: quietly(async ({ event }) => {
      if (!RECORDED_EVENTS.has(event.type)) return
      record(event.type, { sessionID: sessionOf(event), ...event.properties })
      if (event.type === "session.idle") await dumpTranscript(sessionOf(event))
    }),

    "chat.message": quietly(async (input, output) =>
      record("chat.message", { sessionID: input.sessionID, ...output }),
    ),

    "tool.execute.before": quietly(async (input, output) =>
      record("tool.execute.before", { ...input, args: output.args }),
    ),

    "tool.execute.after": quietly(async (input, output) =>
      record("tool.execute.after", { ...input, result: output }),
    ),

    "permission.ask": quietly(async (input, output) =>
      record("permission.ask", { sessionID: input.sessionID, permission: input, status: output.status }),
    ),

    "shell.env": quietly(async (_input, output) => {
      output.env.AGENT_TELEMETRY_BIN = BIN
    }),
  }
}
