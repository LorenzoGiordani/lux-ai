# Worker CF `lux-paper-cron` — trigger xsection-precompute

**TODO operativo**: aggiungere il trigger del workflow `xsection-precompute.yml`
alla schedulazione del Worker Cloudflare `lux-paper-cron` (lo scheduler che
dispatcha i workflow GitHub via `workflow_dispatch`, perché lo schedule nativo
salta i repo privati).

Il workflow `xsection-precompute.yml` esiste nel repo ma oggi viene dispatchato
solo manualmente. La cache `data/xsection/` è già committata e fresca, ma senza
trigger periodico **stagna** → `glm-regime-confluence` (CORE = tsmom + xsection)
degrada la via preferenziale (tsmom+xsection allineati) e resta solo sulla via
di fallback (tsmom + conviction alto).

## Perché dal Worker e non dal cron nativo
Lo stesso pattern di `kronos-precompute` (`30 5 * * *`), `gdelt-precompute`
(`45 */6`) e il `paper-run` orario: il Worker CF è il clock affidabile del
progetto (GitHub Actions schedule salta i repo privati).

## Come deployare (richiede CF API token)

Il codice sorgente del Worker NON è in questo repo (deploy separato). Per
aggiungere il trigger, recupera il worker esistente e aggiungi uno step di
dispatch con cron orario o ogni 6h (xsection è leggero, ~30s):

```bash
# 1. recupera il worker corrente (se servisse ispezionarlo)
npx wrangler@4 deployments list --name lux-paper-cron
npx wrangler@4 tail lux-paper-cron   # vedi i dispatch live

# 2. il Worker dispatcha i workflow via API GitHub. Aggiungi nel codice del
#    Worker un cron handler che dispatcha xsection, esempio (adatta alla
#    sintassi del Worker esistente):
#
#    // ogni 6 ore: refresh cache xsection (leggero)
#    scheduled(event, env, ctx) {
#      const h = new Date(event.scheduledTime).getUTCHours();
#      if (h % 6 === 0) {
#        ctx.waitUntil(dispatchGH(env, "xsection-precompute.yml"));
#      }
#      ... (paper-run, kronos, gdelt già presenti)
#    }
```

`dispatchGH(env, workflow)` è l'helper già usato dagli altri trigger nel Worker
(POST `https://api.github.com/repos/LorenzoGiordani/lux-ai/actions/workflows/
<workflow>/dispatches` con `GH_PAT` come bearer).

## Frequenza consigliata
`xsection-precompute` legge `data/candles/` (già freschi via hl-snapshot) e
ricalcola i rank cross-sectional: ~30s. Ogni **6 ore** basta (come gdelt). La
cache si commita nel workflow stesso.

## Verifica post-deploy
```bash
gh run list --workflow xsection-precompute.yml --limit 3
git log -1 --format="%ci" -- data/xsection/BTC.parquet   # deve avanzare
```

## Nota di sicurezza
Il Worker usa `GH_PAT` + `CLOUDFLARE_API_TOKEN` (entrambi da **ruotare** —
esposti in chat durante il setup 17/06). Aggiornare il trigger è occasione
buona per ruotarli.
