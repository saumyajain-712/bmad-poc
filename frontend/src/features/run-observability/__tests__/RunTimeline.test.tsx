import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import RunTimeline from '../RunTimeline';

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
});
