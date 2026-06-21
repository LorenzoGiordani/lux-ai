// Cron Worker per il paper trading di GitHub Actions (lo scheduler nativo GitHub
// salta/ritarda le run su repo privato; questo Worker è il clock affidabile).
//
// Due compiti:
//  1) HOURLY (cron "10 * * * *") → dispatch del paper-run completo (segnali, LLM, dashboard)
//  2) MONITOR (cron "*/3 * * * *") → legge le posizioni aperte, controlla i mid HL e,
//     SOLO se uno stop/target è sfiorato, dispatcha paper-exits.yml → uscite ~real-time
//     con minuti Actions quasi nulli (GitHub gira solo sui breach reali).
//
// Secret richiesto: GH_PAT — PAT fine-grained con permesso Actions: write sul repo.

const REPO = "LorenzoGiordani/lux-ai"; // repo rinominato da defi-ai-vault
const HOURLY_CRON = "10 * * * *";
const KRONOS_CRON = "30 5 * * *"; // 1x/giorno: rigenera la cache forecast Kronos (lux-0.1-beta)
const GDELT_CRON = "45 */6 * * *"; // 4x/giorno: rinfresca la cache eventi GDELT (desk geopolitics-v1)

async function dispatch(env, workflow) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lux-paper-cron",
      },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  const ok = res.status === 204; // 204 No Content = dispatch riuscito
  if (!ok) console.log(`dispatch ${workflow} failed`, res.status, await res.text());
  return ok;
}

// legge lo stato paper e i mid HL; se una posizione crypto ha sfiorato stop/target
// lancia paper-exits. Le commodity (xyz_*) non sono su HL → restano all'hourly run.
async function monitor(env) {
  const sres = await fetch(
    `https://api.github.com/repos/${REPO}/contents/paper/state.json?ref=main`,
    {
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lux-paper-cron",
      },
    },
  );
  if (!sres.ok) { console.log("state fetch failed", sres.status); return false; }
  const state = await sres.json();

  const pos = [];
  for (const sid in state) {
    const ps = (state[sid] && state[sid].positions) || {};
    for (const sym in ps) {
      if (sym.startsWith("xyz_")) continue; // commodity: niente feed real-time
      const p = ps[sym];
      pos.push({ sym, dir: p.direction, stop: p.stop_px, tgt: p.target_px });
    }
  }
  if (!pos.length) return false;

  const mres = await fetch("https://api.hyperliquid.xyz/info", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "allMids" }),
  });
  if (!mres.ok) { console.log("mids fetch failed", mres.status); return false; }
  const mids = await mres.json();

  const hit = pos.filter((p) => {
    const m = parseFloat(mids[p.sym]);
    if (!isFinite(m)) return false;
    return p.dir === "long" ? (m <= p.stop || m >= p.tgt) : (m >= p.stop || m <= p.tgt);
  });
  if (!hit.length) return false;

  console.log("breach:", hit.map((h) => h.sym).join(","), "→ dispatch paper-exits");
  return dispatch(env, "paper-exits.yml");
}

export default {
  async scheduled(event, env, ctx) {
    if (event.cron === HOURLY_CRON) ctx.waitUntil(dispatch(env, "paper-run.yml"));
    else if (event.cron === KRONOS_CRON) ctx.waitUntil(dispatch(env, "kronos-precompute.yml"));
    else if (event.cron === GDELT_CRON) ctx.waitUntil(dispatch(env, "gdelt-precompute.yml"));
    else ctx.waitUntil(monitor(env));
  },
  // GET manuale: ?run forza il paper-run, default = esegue il monitor (utile per test)
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.searchParams.has("run")) {
      const ok = await dispatch(env, "paper-run.yml");
      return new Response(ok ? "paper-run dispatched\n" : "dispatch failed\n", { status: ok ? 200 : 502 });
    }
    const fired = await monitor(env);
    return new Response(fired ? "breach → paper-exits dispatched\n" : "monitor ok, nessun breach\n", { status: 200 });
  },
};
