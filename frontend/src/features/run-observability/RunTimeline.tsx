import React from 'react';
import type { RunTimelineEvent } from '../../services/bmadService';

interface RunTimelineProps {
  events: RunTimelineEvent[];
}

const formatEventDetail = (event: RunTimelineEvent): string => {
  if (event.event_type === 'phase-status-changed') {
    return `${event.old_status || 'unknown'} -> ${event.new_status || 'unknown'} (${event.reason || 'n/a'})`;
  }

  if (event.previous_phase || event.next_phase) {
    return `${event.previous_phase || 'start'} -> ${event.next_phase || 'n/a'}`;
  }

  if (event.context_source || event.context_version !== undefined) {
    return `source: ${event.context_source || 'n/a'}, version: ${event.context_version ?? 'n/a'}`;
  }

  if (event.error_summary) {
    return event.error_summary;
  }

  return event.reason || 'No additional detail';
};

const formatTimestamp = (timestamp?: string): string => timestamp || 'timestamp unavailable';

const eventKey = (event: RunTimelineEvent, index: number): string => (
  `${event.timestamp || 'na'}-${event.event_type}-${event.phase || 'na'}-${index}`
);

const RunTimeline: React.FC<RunTimelineProps> = ({ events }) => {
  if (!Array.isArray(events) || events.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Run timeline"
      style={{
        borderTop: '1px solid #d9edf7',
        marginTop: 10,
        paddingTop: 10,
      }}
    >
      <p style={{ marginTop: 0 }}>
        <strong>Run timeline</strong>
      </p>
      <ul style={{ marginBottom: 0 }}>
        {events.map((event, index) => (
          <li key={eventKey(event, index)}>
            <strong>{formatTimestamp(event.timestamp)}</strong>
            {' | '}
            {event.phase || 'unscoped'}
            {' | '}
            {event.event_type}
            {' | '}
            {formatEventDetail(event)}
          </li>
        ))}
      </ul>
    </section>
  );
};

export default RunTimeline;
