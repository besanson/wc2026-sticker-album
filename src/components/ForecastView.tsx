import { useMemo, useState } from 'react';
import { useApp, albumStats } from '../state';
import { calibrateCollationFactor, expectedPacksToComplete, forecast } from '../lib/forecast';
import { findTrades } from '../lib/trade';
import type { ForecastModel } from '../lib/forecast';

export function ForecastView() {
  const { catalog, album, packsPurchased, setPacksPurchased, users, profile, proposedTradeAcceptances } = useApp();
  const [model, setModel] = useState<ForecastModel>('collated');
  const [observedPacks, setObservedPacks] = useState(110);
  const [observedRepeatPct, setObservedRepeatPct] = useState(12);
  const stats = albumStats(album, catalog);

  const proposedTrades = useMemo(() => {
    if (proposedTradeAcceptances.length === 0) return { tradedIn: [] as number[], tradedOut: [] as number[] };
    const matches = findTrades(album, catalog, users, profile?.coords, {});
    const byId = new Map(matches.map(m => [m.user.id, m]));
    const tradedIn = new Set<number>();
    const tradedOut = new Set<number>();
    for (const uid of proposedTradeAcceptances) {
      const m = byId.get(uid);
      if (!m) continue;
      // Cap each side at min(give, receive) to keep trades balanced 1-for-1.
      const k = Math.min(m.iCanGive.length, m.iCanReceive.length);
      m.iCanReceive.slice(0, k).forEach(id => tradedIn.add(id));
      m.iCanGive.slice(0, k).forEach(id => tradedOut.add(id));
    }
    return { tradedIn: [...tradedIn], tradedOut: [...tradedOut] };
  }, [album, catalog, users, profile, proposedTradeAcceptances]);

  const calibratedFactor = useMemo(() => {
    return calibrateCollationFactor(catalog.total, catalog.stickersPerPack, observedPacks, observedRepeatPct / 100);
  }, [catalog.total, catalog.stickersPerPack, observedPacks, observedRepeatPct]);

  const result = useMemo(() => forecast({
    catalog, album,
    plannedPacks: packsPurchased,
    tradedIn: proposedTrades.tradedIn,
    tradedOut: proposedTrades.tradedOut,
    model,
    collationFactor: calibratedFactor,
    trials: 600,
  }), [catalog, album, packsPurchased, proposedTrades, model, calibratedFactor]);

  const baseline = expectedPacksToComplete(catalog, stats.owned, model, calibratedFactor);
  const incrementalDuplicates = Math.max(0, result.expectedDuplicates - stats.duplicates);
  const projectedRepeatRate = result.draws > 0 ? incrementalDuplicates / result.draws : 0;

  // Histogram: bucket the per-trial completion %.
  const histogram = useMemo(() => {
    const buckets = new Array(20).fill(0); // 0–5, 5–10 ... 95–100
    for (const v of result.perTrialCompletionPct) {
      const idx = Math.min(19, Math.max(0, Math.floor(v / 5)));
      buckets[idx]++;
    }
    return buckets;
  }, [result]);

  const histMax = Math.max(...histogram, 1);

  return (
    <div className="stack-lg">
      <header className="card card-pad">
        <h2>Completion forecast</h2>
        <div className="sub">
          A Monte Carlo simulation estimates how many unique stickers you should have after the packs you plan to buy, plus any selected demo trades. The default model reflects real-world pack collation, so early packs are not treated as fully independent random draws.
        </div>
      </header>

      <div className="forecast-grid">
        <div className="card card-pad stack">
          <div className="field">
            <label htmlFor="packs">Packs you plan to buy</label>
            <div className="row gap-3" style={{ alignItems: 'center' }}>
              <input
                id="packs"
                type="range" min={0} max={1500} step={5}
                value={packsPurchased}
                onChange={e => setPacksPurchased(Number(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--accent)' }}
                aria-valuemin={0} aria-valuemax={1500} aria-valuenow={packsPurchased}
              />
              <input
                type="number" min={0} max={2000} value={packsPurchased}
                onChange={e => setPacksPurchased(Number(e.target.value))}
                className="input" style={{ width: 84 }} aria-label="Packs (number)"
              />
            </div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
              {result.draws} stickers from packs · starts from {result.startingOwned} owned / {result.startingMissing} missing · approx ${result.expectedSpendUSD.toFixed(2)} at retail
            </div>
          </div>

          <div className="field">
            <label htmlFor="forecast-model">Forecast model</label>
            <select
              id="forecast-model"
              className="select"
              value={model}
              onChange={e => setModel(e.target.value as ForecastModel)}
            >
              <option value="collated">Realistic collation (recommended)</option>
              <option value="uniform">Conservative uniform draw</option>
            </select>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
              {model === 'collated'
                ? 'Uses your observed repeat rate to tune early-pack collation.'
                : 'Pure coupon-collector math. Useful as a pessimistic baseline, but usually too harsh for early sealed-pack collecting.'}
            </div>
          </div>

          {model === 'collated' && (
            <div className="notice">
              <b>Your calibration</b>
              <div className="row gap-3 mt-2" style={{ flexWrap: 'wrap' }}>
                <div className="field" style={{ minWidth: 150, flex: '1 1 150px' }}>
                  <label htmlFor="observed-packs">Packs opened</label>
                  <input
                    id="observed-packs"
                    type="number"
                    min={1}
                    max={2000}
                    className="input"
                    value={observedPacks}
                    onChange={e => setObservedPacks(Math.max(1, Math.min(2000, Math.floor(Number(e.target.value) || 1))))}
                  />
                </div>
                <div className="field" style={{ minWidth: 150, flex: '1 1 150px' }}>
                  <label htmlFor="observed-repeat">Repeat rate %</label>
                  <input
                    id="observed-repeat"
                    type="number"
                    min={0}
                    max={95}
                    step={0.1}
                    className="input"
                    value={observedRepeatPct}
                    onChange={e => setObservedRepeatPct(Math.max(0, Math.min(95, Number(e.target.value) || 0)))}
                  />
                </div>
              </div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                Calibrated from your observed result: {observedPacks} packs × {catalog.stickersPerPack} stickers, with about {observedRepeatPct.toFixed(1)}% repeats. Collation strength: {calibratedFactor.toFixed(2)}.
              </div>
            </div>
          )}

          <div className="kpi-grid mt-2">
            <div className="kpi">
              <div className="k-label">Expected completion</div>
              <div className="k-value">{result.mean.toFixed(1)}%</div>
              <div className="k-sub">P10 {result.p10.toFixed(0)}% — P90 {result.p90.toFixed(0)}%</div>
            </div>
            <div className="kpi">
              <div className="k-label">Probability of full set</div>
              <div className="k-value">{(result.pComplete * 100).toFixed(1)}%</div>
              <div className="k-sub">across {result.trials} sims</div>
            </div>
            <div className="kpi">
              <div className="k-label">Expected duplicates</div>
              <div className="k-value">{result.expectedDuplicates.toFixed(0)}</div>
              <div className="k-sub">{(projectedRepeatRate * 100).toFixed(1)}% repeats in these packs</div>
            </div>
            <div className="kpi">
              <div className="k-label">Expected packs needed*</div>
              <div className="k-value">{baseline.toFixed(0)}</div>
              <div className="k-sub">additional packs, {model === 'collated' ? 'collated' : 'uniform'} model</div>
            </div>
          </div>

          <div className="mt-3">
            <div className="bar-h">
              <div className="label">Current <b>{stats.completionPct.toFixed(1)}%</b><span>·</span><span>Expected after spend <b className="tabular">{result.mean.toFixed(1)}%</b></span></div>
              <div className="progress-track" aria-label="forecast bar">
                <div className="progress-bicolor" style={{ width: `${result.mean.toFixed(2)}%`, background: 'linear-gradient(90deg, var(--accent), var(--gold))' }} />
              </div>
            </div>
          </div>
        </div>

        <div className="card card-pad">
          <h3 style={{ marginBottom: 8 }}>Distribution of outcomes</h3>
          <div className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>Each bar is the count of simulated runs landing in that 5-point completion band.</div>
          <div className="histogram" aria-label="completion distribution">
            {histogram.map((v, i) => {
              const top = (v / histMax) * 100;
              const isTarget = i === 19; // 95–100% bucket
              return <div key={i} className={`bar ${isTarget ? 'target' : ''}`} style={{ height: `${Math.max(2, top)}%` }} title={`${i*5}–${Math.min(100, (i+1)*5)}% · ${v} runs`} />;
            })}
          </div>
          <div className="row" style={{ justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>0%</span><span>50%</span><span>100%</span>
          </div>

          <h3 style={{ margin: '16px 0 6px' }}>Assumptions</h3>
          <ul className="assumption-list">
            <li><b>Realistic collation</b> is calibrated from your observed repeat rate: {observedPacks} packs and {observedRepeatPct.toFixed(1)}% repeats. Switch to uniform for a conservative coupon-collector baseline.</li>
            <li>Stickers per pack: <b>{catalog.stickersPerPack}</b>. Retail estimate: <b>${catalog.retailPackPriceUSD.toFixed(2)}</b> per pack.</li>
            <li>Expected missing after this scenario: <b>{result.expectedMissing.toFixed(0)}</b> stickers. {result.observedDuplicateRate !== null ? <>Your entered album currently shows <b>{(result.observedDuplicateRate * 100).toFixed(1)}%</b> duplicates.</> : 'Enter duplicate counts in the album to compare the forecast with your real duplicate rate.'}</li>
            <li>Trades you've proposed count as 1-for-1 swaps and are applied to the starting set before drawing packs.</li>
            <li>Each scenario runs <b>{result.trials}</b> simulated trials. The histogram bins outcomes in 5% bands.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
