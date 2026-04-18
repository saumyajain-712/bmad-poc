import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import RunTimeline from '../RunTimeline';
import { redactSensitivePatterns, summarizeToolPayload } from '../toolEventPresentation';
import { TOOL_CALL_COMPLETED_EVENT_TYPE } from '../../../services/bmadService';

describe('RunTimeline', () => {
  it('renders timeline rows in provided order with required columns', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: 'context-resolved',
            phase: 'prd',
            context_source: 'resolved_input_context',
            context_version: 1,
            timestamp: '2026-04-17T16:00:00Z',
          },
          {
            event_type: 'phase-status-changed',
            phase: 'prd',
            old_status: 'pending',
            new_status: 'in-progress',
            reason: 'phase started',
            timestamp: '2026-04-17T16:00:01Z',
          },
        ]}
      />
    );

    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('2026-04-17T16:00:00Z | prd | context-resolved');
    expect(rows[1]).toHaveTextContent('2026-04-17T16:00:01Z | prd | phase-status-changed');
  });

  it('appends new events without dropping existing rows', () => {
    const initialEvents = [
      {
        event_type: 'context-resolved',
        phase: 'prd',
        context_source: 'resolved_input_context',
        context_version: 1,
        timestamp: '2026-04-17T16:00:00Z',
      },
    ];

    const { rerender } = render(<RunTimeline events={initialEvents} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(1);

    rerender(
      <RunTimeline
        events={[
          ...initialEvents,
          {
            event_type: 'phase-approved',
            phase: 'prd',
            previous_phase: 'prd',
            next_phase: 'architecture',
            timestamp: '2026-04-17T16:00:02Z',
          },
        ]}
      />
    );

    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('context-resolved');
    expect(rows[1]).toHaveTextContent('phase-approved');
  });

  it('renders tool-call-completed rows with tool label and summaries', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: TOOL_CALL_COMPLETED_EVENT_TYPE,
            phase: 'prd',
            timestamp: '2026-04-17T16:00:05Z',
            tool_name: 'read_file',
            tool_input: { path: 'docs/prd/context.md' },
            tool_output: { lines: 10, preview: 'outline' },
          },
        ]}
      />
    );

    const row = screen.getByRole('listitem');
    expect(row).toHaveTextContent('2026-04-17T16:00:05Z | prd | tool-call-completed');
    expect(row).toHaveTextContent('Tool: read_file');
    expect(row).toHaveTextContent('in:');
    expect(row).toHaveTextContent('out:');
  });

  it('redacts obvious secret-like substrings in tool payload summaries', () => {
    const dirty = '{"token":"Bearer abc123xyz","k":"sk-abcdefghijklmnopqrstuv"}';
    expect(redactSensitivePatterns(dirty)).toContain('[redacted]');
    expect(redactSensitivePatterns(dirty)).not.toContain('Bearer abc123xyz');
    expect(redactSensitivePatterns(dirty)).not.toContain('sk-abcdefghijklmnopqrstuv');
  });

  it('redacts secrets in the rendered tool row (NFR12 presentation path)', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: TOOL_CALL_COMPLETED_EVENT_TYPE,
            phase: 'prd',
            timestamp: '2026-04-17T16:00:05Z',
            tool_name: 'mock_tool',
            tool_input: { scope: 'ok' },
            tool_output: {
              token: 'Bearer verysecrettoken',
              key: 'sk-abcdefghijklmnopqrstuv',
            },
          },
        ]}
      />
    );

    const row = screen.getByRole('listitem');
    expect(row.textContent).toContain('[redacted]');
    expect(row.textContent).not.toContain('verysecrettoken');
    expect(row.textContent).not.toContain('sk-abcdefghijklmnopqrstuv');
  });

  it('summarizeToolPayload does not throw on BigInt or circular values', () => {
    expect(summarizeToolPayload({ n: BigInt(99) })).toContain('99');
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(summarizeToolPayload(circular)).toBe('[unserializable]');
  });

  it('renders fallback labels when timestamp or phase are missing', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: 'context-resolved',
            context_version: 1,
          },
        ]}
      />
    );

    const row = screen.getByRole('listitem');
    expect(row).toHaveTextContent('timestamp unavailable');
    expect(row).toHaveTextContent('unscoped');
    expect(row).toHaveTextContent('context-resolved');
    expect(row).toHaveTextContent('source: n/a, version: 1');
  });
});
