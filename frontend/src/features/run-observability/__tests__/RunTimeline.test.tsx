import { fireEvent, render, screen } from '@testing-library/react';
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

  it('renders web-search tool rows with query and result summaries', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: TOOL_CALL_COMPLETED_EVENT_TYPE,
            phase: 'prd',
            timestamp: '2026-04-17T16:00:06Z',
            tool_name: 'web_search',
            tool_input: { query: 'phase sequencing best practices', limit: 3, provider: 'mock' },
            tool_output: {
              results: [{ title: 'A' }, { title: 'B' }],
              total: 2,
              source: 'simulated',
            },
          },
        ]}
      />
    );

    const row = screen.getByRole('listitem');
    expect(row).toHaveTextContent('Tool: web_search');
    expect(row).toHaveTextContent('query:');
    expect(row).toHaveTextContent('phase sequencing best practices');
    expect(row).toHaveTextContent('results:');
  });

  it('shows full web-search payloads in expanded detail panel', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: TOOL_CALL_COMPLETED_EVENT_TYPE,
            phase: 'prd',
            timestamp: '2026-04-17T16:00:07Z',
            tool_name: 'web_search',
            tool_input: { query: 'web search test query', limit: 3, provider: 'mock' },
            tool_output: {
              results: [
                { title: 'Result 1', snippet: 'First snippet' },
                { title: 'Result 2', snippet: 'Second snippet' },
              ],
              total: 2,
              source: 'simulated',
            },
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Details for/ }));
    const inputPre = screen.getByTestId('tool-input-full');
    expect(inputPre.textContent).toContain('web search test query');
    expect(inputPre.textContent).toContain('"provider": "mock"');
    const outputPre = screen.getByTestId('tool-output-full');
    expect(outputPre.textContent).toContain('"source": "simulated"');
    expect(outputPre.textContent).toContain('Result 1');
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

  it('expands tool event detail with full pretty-printed redacted payloads (AC2, AC4)', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: TOOL_CALL_COMPLETED_EVENT_TYPE,
            phase: 'prd',
            timestamp: '2026-04-17T16:00:05Z',
            tool_name: 'read_file',
            tool_input: { path: 'docs/prd/context.md' },
            tool_output: {
              token: 'Bearer verysecrettoken',
              key: 'sk-abcdefghijklmnopqrstuv',
            },
          },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Details for/ }));
    const inputPre = screen.getByTestId('tool-input-full');
    expect(inputPre.textContent).toContain('"path"');
    expect(inputPre.textContent).toContain('docs/prd/context.md');

    const outPre = screen.getByTestId('tool-output-full');
    expect(outPre.textContent).toContain('[redacted]');
    expect(outPre.textContent).not.toContain('verysecrettoken');
    expect(outPre.textContent).not.toContain('sk-abcdefghijklmnopqrstuv');
  });

  it('expands non-tool event detail with structured fields and debug JSON (AC3)', () => {
    render(
      <RunTimeline
        events={[
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

    fireEvent.click(screen.getByRole('button', { name: /Details for/ }));
    expect(screen.getByText('Old status')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
    expect(screen.getByText('in-progress')).toBeInTheDocument();
    expect(screen.getByText('Reason')).toBeInTheDocument();
    expect(screen.getByText('phase started')).toBeInTheDocument();
    const fullJson = screen.getByTestId('full-event-json');
    expect(fullJson.textContent).toContain('phase-status-changed');
  });

  it('keeps all timeline rows when toggling detail; only inspection UI changes (AC5)', () => {
    const events = [
      {
        event_type: 'context-resolved',
        phase: 'prd',
        timestamp: '2026-04-17T16:00:00Z',
        context_source: 'resolved_input_context',
        context_version: 1,
      },
      {
        event_type: TOOL_CALL_COMPLETED_EVENT_TYPE,
        phase: 'prd',
        timestamp: '2026-04-17T16:00:05Z',
        tool_name: 'read_file',
        tool_input: {},
        tool_output: {},
      },
    ];
    render(<RunTimeline events={events} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);

    fireEvent.click(screen.getAllByRole('button', { name: /Details for/ })[0]);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);

    fireEvent.click(screen.getAllByRole('button', { name: /Hide details for/ })[0]);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.queryByTestId('full-event-json')).not.toBeInTheDocument();
  });

  it('sets aria-expanded on the details control when expanded', () => {
    render(
      <RunTimeline
        events={[
          {
            event_type: 'phase-status-changed',
            phase: 'prd',
            old_status: 'a',
            new_status: 'b',
            timestamp: 't',
          },
        ]}
      />
    );
    const btn = screen.getByRole('button', { name: /Details for/ });
    expect(btn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
  });

  it('collapses detail if the expanded event is no longer present after refresh', () => {
    const initialEvents = [
      {
        event_type: 'phase-status-changed',
        phase: 'prd',
        old_status: 'pending',
        new_status: 'in-progress',
        timestamp: '2026-04-17T16:00:01Z',
      },
    ];
    const { rerender } = render(<RunTimeline events={initialEvents} />);

    fireEvent.click(screen.getByRole('button', { name: /Details for/ }));
    expect(screen.getByTestId('event-detail-panel')).toBeInTheDocument();

    rerender(
      <RunTimeline
        events={[
          {
            event_type: 'context-resolved',
            phase: 'prd',
            timestamp: '2026-04-17T16:00:00Z',
            context_source: 'resolved_input_context',
            context_version: 1,
          },
        ]}
      />
    );

    expect(screen.queryByTestId('event-detail-panel')).not.toBeInTheDocument();
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
