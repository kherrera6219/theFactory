'use client';

import React from 'react';
import { compareQuotedActual, type QuotedFactoryCost } from '../../../../../lib/cost-quote';
import { Panel } from '../../../../../components/panel';
import type { LlmUsageSummary } from '../../../../../lib/types';

interface CostPanelProps {
  tokenUsage: LlmUsageSummary | null;
  quoted?: QuotedFactoryCost | null;
}

export function CostPanel({ tokenUsage, quoted }: CostPanelProps) {
  const comparison = compareQuotedActual(quoted, tokenUsage?.estimated_cost_usd ?? null);
  if ((!tokenUsage || tokenUsage.call_count === 0) && !comparison.pricingKnown) return null;

  return (
    <Panel title="Token Usage & Cost Analysis" className="cost-analysis-panel">
      {comparison.pricingKnown && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            marginBottom: '20px',
          }}
        >
          <div className="card" style={{ padding: '16px', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '8px' }}>
            <p className="help-text" style={{ margin: 0, textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Quoted (SOW)
            </p>
            <h3 style={{ fontSize: '1.75rem', fontWeight: 'bold', margin: '8px 0 0 0', color: 'var(--text-primary)' }}>
              {comparison.quotedLikely != null ? `$${comparison.quotedLikely.toFixed(4)}` : 'n/a'}
            </h3>
            <p className="help-text" style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              High {comparison.quotedHigh != null ? `$${comparison.quotedHigh.toFixed(4)}` : 'n/a'} · Cap{' '}
              {comparison.quotedCap != null ? `$${comparison.quotedCap.toFixed(4)}` : 'n/a'}
            </p>
          </div>
          <div className="card" style={{ padding: '16px', background: comparison.overCap ? 'rgba(239, 68, 68, 0.12)' : 'rgba(15, 23, 42, 0.4)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '8px' }}>
            <p className="help-text" style={{ margin: 0, textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em', color: comparison.overCap ? '#f87171' : 'var(--text-muted)' }}>
              vs Cap
            </p>
            <h3 style={{ fontSize: '1.75rem', fontWeight: 'bold', margin: '8px 0 0 0', color: comparison.overCap ? '#f87171' : '#10b981' }}>
              {comparison.remainingToCap == null
                ? 'n/a'
                : comparison.overCap
                  ? `Over by $${Math.abs(comparison.remainingToCap).toFixed(4)}`
                  : `$${comparison.remainingToCap.toFixed(4)} left`}
            </h3>
            <p className="help-text" style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              This is model spend for this run, not a human project quote.
            </p>
          </div>
        </div>
      )}
      {(!tokenUsage || tokenUsage.call_count === 0) ? null : (
      <>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginBottom: '20px',
        }}
      >
        <div
          className="card"
          style={{
            padding: '16px',
            background: 'rgba(139, 92, 246, 0.08)',
            border: '1px solid rgba(139, 92, 246, 0.2)',
            borderRadius: '8px',
          }}
        >
          <p
            className="help-text"
            style={{
              margin: 0,
              textTransform: 'uppercase',
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              color: '#a78bfa',
            }}
          >
            Estimated Cost
          </p>
          <h3 style={{ fontSize: '1.75rem', fontWeight: 'bold', margin: '8px 0 0 0', color: '#10b981' }}>
            {tokenUsage.estimated_cost_usd !== null
              ? `$${tokenUsage.estimated_cost_usd.toFixed(4)}`
              : 'n/a'}
          </h3>
          <p className="help-text" style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {tokenUsage.unknown_pricing_count > 0
              ? `(${tokenUsage.unknown_pricing_count} calls unpriced)`
              : comparison.varianceVsLikely != null
                ? `Actual vs likely ${comparison.varianceVsLikely >= 0 ? '+' : ''}$${comparison.varianceVsLikely.toFixed(4)}`
                : 'All calls priced'}
          </p>
        </div>

        <div
          className="card"
          style={{
            padding: '16px',
            background: 'rgba(15, 23, 42, 0.4)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
          }}
        >
          <p
            className="help-text"
            style={{
              margin: 0,
              textTransform: 'uppercase',
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              color: 'var(--text-muted)',
            }}
          >
            Total Token Volume
          </p>
          <h3 style={{ fontSize: '1.75rem', fontWeight: 'bold', margin: '8px 0 0 0', color: 'var(--text-primary)' }}>
            {tokenUsage.total_tokens.toLocaleString()}
          </h3>
          <p className="help-text" style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {tokenUsage.total_input_tokens.toLocaleString()} in /{' '}
            {tokenUsage.total_output_tokens.toLocaleString()} out
          </p>
        </div>

        <div
          className="card"
          style={{
            padding: '16px',
            background: 'rgba(15, 23, 42, 0.4)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
          }}
        >
          <p
            className="help-text"
            style={{
              margin: 0,
              textTransform: 'uppercase',
              fontSize: '0.75rem',
              letterSpacing: '0.05em',
              color: 'var(--text-muted)',
            }}
          >
            LLM Delegations
          </p>
          <h3 style={{ fontSize: '1.75rem', fontWeight: 'bold', margin: '8px 0 0 0', color: 'var(--text-primary)' }}>
            {tokenUsage.call_count}
          </h3>
          <p className="help-text" style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Active agent calls
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        <div>
          <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '12px', color: 'var(--text-primary)' }}>
            Usage by Provider & Model
          </h4>
          <div className="table-wrap" style={{ margin: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Provider/Model</th>
                  <th scope="col" style={{ textAlign: 'right' }}>
                    Tokens (In / Out)
                  </th>
                  <th scope="col" style={{ textAlign: 'right' }}>
                    Cost (USD)
                  </th>
                </tr>
              </thead>
              <tbody>
                {tokenUsage.by_provider.map((prov, i) => (
                  <tr key={i}>
                    <td>
                      <span style={{ fontWeight: '500', textTransform: 'capitalize' }}>{prov.provider}</span>
                      <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>
                        {prov.model}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <span>{(prov.input_tokens + prov.output_tokens).toLocaleString()}</span>
                      <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>
                        {prov.input_tokens.toLocaleString()} / {prov.output_tokens.toLocaleString()}
                      </span>
                    </td>
                    <td
                      style={{
                        textAlign: 'right',
                        fontWeight: '500',
                        color: prov.estimated_cost_usd !== null ? '#10b981' : 'inherit',
                      }}
                    >
                      {prov.estimated_cost_usd !== null ? `$${prov.estimated_cost_usd.toFixed(4)}` : 'n/a'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '12px', color: 'var(--text-primary)' }}>
            Usage by Assigned Agent
          </h4>
          <div className="table-wrap" style={{ margin: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Agent ID</th>
                  <th scope="col" style={{ textAlign: 'right' }}>
                    Tokens (In / Out)
                  </th>
                  <th scope="col" style={{ textAlign: 'right' }}>
                    Cost (USD)
                  </th>
                </tr>
              </thead>
              <tbody>
                {tokenUsage.by_agent.map((agent, i) => (
                  <tr key={i}>
                    <td>
                      <span style={{ fontWeight: '500' }}>{agent.agent_id}</span>
                      <span className="muted" style={{ display: 'block', fontSize: '0.8rem', textTransform: 'capitalize' }}>
                        {agent.provider} ({agent.model})
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <span>{(agent.input_tokens + agent.output_tokens).toLocaleString()}</span>
                      <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>
                        {agent.input_tokens.toLocaleString()} / {agent.output_tokens.toLocaleString()}
                      </span>
                    </td>
                    <td
                      style={{
                        textAlign: 'right',
                        fontWeight: '500',
                        color: agent.cost_usd !== null ? '#10b981' : 'inherit',
                      }}
                    >
                      {agent.cost_usd !== null ? `$${agent.cost_usd.toFixed(4)}` : 'n/a'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      </>
      )}
    </Panel>
  );
}
