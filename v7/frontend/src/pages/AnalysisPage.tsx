import React, { FormEvent, useState } from 'react';
import { useAtom } from 'jotai';
import { selectedSymbolAtom } from '../state/selectionAtom';
import { useDebateStream } from '../hooks/useDebateStream';
import { DebateTurnCard } from '../components/streaming/DebateTurnCard';

export const AnalysisPage: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useAtom(selectedSymbolAtom);
  const [symbolInput, setSymbolInput] = useState(selectedSymbol ?? '');
  const { state: stream, startStream, reset } = useDebateStream();

  const isRunning = stream.status === 'connecting' || stream.status === 'streaming';
  const error = stream.status === 'error' ? (stream.error ?? 'Stream error') : null;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!symbolInput.trim()) return;
    const symbol = symbolInput.trim().toUpperCase();
    setSelectedSymbol(symbol);
    reset();
    startStream({ ticker: symbol, timeframe: '3 months', min_rounds: 1, max_rounds: 5 });
  };

  function verdictColor(rec: string | null): string {
    if (!rec) return 'text-muted-foreground';
    const u = rec.toUpperCase();
    if (u.includes('BUY')) return 'text-success';
    if (u.includes('SELL')) return 'text-destructive';
    if (u.includes('NO_DECISION')) return 'text-muted-foreground italic';
    return 'text-warning';
  }

  return (
    <section className="space-y-6 animate-fade-in">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Multi-Agent Debate</h1>
        <p className="text-base text-muted-foreground max-w-2xl">
          Run structured AI-powered debates between fundamental, technical, and sentiment analysts. Get comprehensive investment insights powered by generative AI.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr,2fr]">
        {/* Input Card */}
        <div className="lg:col-span-1">
          <form
            onSubmit={onSubmit}
            className="space-y-3 rounded-lg border border-border/50 bg-gradient-soft p-4 shadow-sm hover:shadow-md transition-shadow"
          >
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5" htmlFor="symbol">
                <span className="fa-solid fa-magnifying-glass mr-2" />
                Stock Symbol (VN30)
              </label>
              <input
                id="symbol"
                name="symbol"
                placeholder="e.g., MBB, VCB, TCB, VNM, HPG"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                className="w-full rounded-md border border-border bg-white dark:bg-slate-900 px-3 py-2 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-primary focus:ring-offset-2 dark:focus:ring-offset-slate-950 placeholder-muted-foreground font-medium"
              />
            </div>
            <button
              type="submit"
              className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-gradient-primary px-3 py-2 text-xs font-semibold text-white shadow-md hover:shadow-lg hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isRunning}
            >
              <span className="fa-solid fa-scale-balanced" aria-hidden="true" />
              <span>{isRunning ? 'Running Debate…' : 'Start Debate'}</span>
            </button>
            
              {selectedSymbol && !isRunning && (
              <div className="pt-2 border-t border-border/30">
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{selectedSymbol}</span> selected
                </p>
              </div>
            )}
          </form>
        </div>

        {/* Results Card */}
        <div className="lg:col-span-1">
          <div className="space-y-3 rounded-lg border border-border/50 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <div>
              <h2 className="text-base font-semibold text-foreground mb-1">
                <span className="fa-solid fa-comments mr-2 text-primary" />
                Debate Transcript
              </h2>
              <p className="text-xs text-muted-foreground">Live analysis from AI agents</p>
            </div>

            <div className="space-y-2">
              {!selectedSymbol && (
                <div className="rounded-md bg-primary-light p-3 border border-primary/20">
                  <p className="text-xs text-foreground/80 font-medium">
                    <span className="fa-solid fa-lightbulb mr-2 text-primary" />
                    Enter a ticker symbol to begin the multi-agent debate
                  </p>
                </div>
              )}

              {selectedSymbol && stream.status === 'idle' && (
                <div className="rounded-md bg-success-light p-3 border border-success/20">
                  <p className="text-xs text-foreground/80 font-medium">
                    Ready to debate <span className="font-semibold text-success">{selectedSymbol}</span>
                  </p>
                </div>
              )}

              {isRunning && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-primary rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-success rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                    <p className="text-xs font-medium text-foreground">
                      Round {stream.currentRound}{stream.maxRounds > 0 ? `/${stream.maxRounds}` : ''} — agents deliberating…
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">Streaming live analysis for {selectedSymbol}</p>
                </div>
              )}

              {error && (
                <div className="rounded-md bg-destructive-light p-3 border border-destructive/20">
                  <p className="text-xs text-destructive font-medium">
                    <span className="fa-solid fa-circle-exclamation mr-2" />
                    {error}
                  </p>
                </div>
              )}

              {/* Live streaming turns */}
              {stream.turns.length > 0 && (
                <div className="space-y-2">
                  {/* Round progress */}
                  {stream.maxRounds > 0 && (
                    <div>
                      <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                        <span>Round {stream.currentRound} of {stream.maxRounds}</span>
                        {stream.confidencePercent !== null && (
                          <span>Confidence: {stream.confidencePercent.toFixed(0)}%</span>
                        )}
                      </div>
                      <div className="h-1 rounded-full bg-border/40 overflow-hidden">
                        <div
                          className="h-full bg-gradient-primary rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, (stream.currentRound / stream.maxRounds) * 100)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Turn cards */}
                  {stream.turns.map((turn) => (
                    <DebateTurnCard key={turn.id} turn={turn} />
                  ))}

                  {/* Final verdict */}
                  {stream.status === 'completed' && stream.finalRecommendation && (
                    <div className={`rounded-lg border-2 p-4 mt-3 ${
                      stream.decisionQualified
                        ? stream.finalRecommendation.toUpperCase().includes('BUY')
                          ? 'border-success/50 bg-success/5'
                          : stream.finalRecommendation.toUpperCase().includes('SELL')
                          ? 'border-destructive/50 bg-destructive/5'
                          : 'border-warning/50 bg-warning/5'
                        : 'border-border/50 bg-muted/30'
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Final Verdict</p>
                        <span className="text-[10px] font-medium rounded-full px-2 py-0.5 bg-muted/60 text-muted-foreground">
                          {stream.actualRounds} round{stream.actualRounds !== 1 ? 's' : ''}
                        </span>
                      </div>
                      <p className={`text-xl font-black mb-1 ${verdictColor(stream.finalRecommendation)}`}>
                        {stream.finalRecommendation}
                      </p>
                      {stream.confidencePercent !== null && (
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs text-muted-foreground">
                            Confidence: <span className="font-semibold text-foreground">{stream.confidencePercent.toFixed(0)}%</span>
                          </span>
                          {stream.decisionQualified ? (
                            <span className="inline-flex items-center gap-1 text-[10px] bg-success/15 text-success rounded-full px-2 py-0.5 font-semibold">
                              <span className="fa-solid fa-circle-check" aria-hidden="true" /> Qualified
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] bg-muted/60 text-muted-foreground rounded-full px-2 py-0.5">
                              Below 80% threshold
                            </span>
                          )}
                        </div>
                      )}
                      {stream.rationale && (
                        <p className="text-xs text-foreground/80 leading-relaxed mt-1">{stream.rationale}</p>
                      )}
                      {stream.risks && (
                        <p className="text-xs text-muted-foreground mt-2">
                          <span className="font-semibold">Risks:</span> {stream.risks}
                        </p>
                      )}
                      {stream.monitor && (
                        <p className="text-xs text-muted-foreground mt-1">
                          <span className="font-semibold">Monitor:</span> {stream.monitor}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};


