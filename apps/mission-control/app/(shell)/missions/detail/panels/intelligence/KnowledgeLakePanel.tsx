'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface FetchResult {
  indexed_languages?: string[];
  skipped_languages?: string[];
  knowledge_ready: boolean;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  refresh_enabled?: boolean;
  refreshed_languages?: string[];
  unchanged_languages?: string[];
  errors?: string[];
}

interface KnowledgeLakePanelProps {
  fetchResult: FetchResult | null;
}

export function KnowledgeLakePanel({ fetchResult }: KnowledgeLakePanelProps) {
  if (!fetchResult) return null;

  return (
    <Panel title="Knowledge Lake (FETCH)">
      <dl>
        <div>
          <dt>Indexed languages</dt>
          <dd>
            {fetchResult.indexed_languages && fetchResult.indexed_languages.length > 0
              ? fetchResult.indexed_languages.join(', ')
              : 'none'}
          </dd>
        </div>
        {fetchResult.skipped_languages && fetchResult.skipped_languages.length > 0 && (
          <div>
            <dt>Skipped (no bootstrap docs)</dt>
            <dd>{fetchResult.skipped_languages.join(', ')}</dd>
          </div>
        )}
        <div>
          <dt>Knowledge ready</dt>
          <dd>{fetchResult.knowledge_ready ? 'Yes' : 'No'}</dd>
        </div>
        <div>
          <dt>Embedding model</dt>
          <dd>
            {fetchResult.embedding_provider && fetchResult.embedding_model
              ? `${fetchResult.embedding_provider}/${fetchResult.embedding_model}`
              : 'deterministic'}
          </dd>
        </div>
        <div>
          <dt>Refresh</dt>
          <dd>{fetchResult.refresh_enabled === false ? 'disabled' : 'enabled'}</dd>
        </div>
        {fetchResult.refreshed_languages && fetchResult.refreshed_languages.length > 0 && (
          <div>
            <dt>Refreshed</dt>
            <dd>{fetchResult.refreshed_languages.join(', ')}</dd>
          </div>
        )}
        {fetchResult.unchanged_languages && fetchResult.unchanged_languages.length > 0 && (
          <div>
            <dt>Unchanged</dt>
            <dd>{fetchResult.unchanged_languages.join(', ')}</dd>
          </div>
        )}
        {fetchResult.errors && fetchResult.errors.length > 0 && (
          <div>
            <dt>Errors</dt>
            <dd className="error-text">{fetchResult.errors.join('; ')}</dd>
          </div>
        )}
      </dl>
    </Panel>
  );
}
