import React, { useEffect, useState } from 'react';
import { TOOL_CALL_COMPLETED_EVENT_TYPE, type RunTimelineEvent } from '../../services/bmadService';
import EventDetailPanel from './EventDetailPanel';
import { summarizeToolPayload } from './toolEventPresentation';

interface RunTimelineProps {
  events: RunTimelineEvent[];
}

const formatEventDetail = (event: RunTimelineEvent): string => {
  if (event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE) {
    const name = event.tool_name || 'unknown_tool';
    if (name === 'web_search') {
      const input = typeof event.tool_input === 'object' && event.tool_input !== null
        ? (event.tool_input as Record<string, unknown>)
        : {};
      const output = typeof event.tool_output === 'object' && event.tool_output !== null
        ? (event.tool_output as Record<string, unknown>)
        : {};
      const querySummary = summarizeToolPayload(input.query ?? '');
      const resultSummary = summarizeToolPayload(output.results ?? []);
      return `Tool: web_search | query: ${querySummary} | results: ${resultSummary}`;
    }
    const inSummary = summarizeToolPayload(event.tool_input);
    const outSummary = summarizeToolPayload(event.tool_output);
    return `Tool: ${name} | in: ${inSummary} | out: ${outSummary}`;
  }

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

/** Only one timeline row shows an expanded detail panel at a time (stable list; toggles inspection only). */
const RunTimeline: React.FC<RunTimelineProps> = ({ events }) => {
  const [expandedEventKey, setExpandedEventKey] = useState<string | null>(null);

  useEffect(() => {
    if (expandedEventKey === null) return;
    const keys = events.map((event, index) => eventKey(event, index));
    if (!keys.includes(expandedEventKey)) {
      setExpandedEventKey(null);
    }
  }, [events, expandedEventKey]);

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
      <ul style={{ marginBottom: 0, paddingLeft: 18 }}>
        {events.map((event, index) => {
          const key = eventKey(event, index);
          const isTool = event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE;
          const expanded = expandedEventKey === key;
          const toggleId = `timeline-event-toggle-${index}`;
          const panelId = `timeline-event-detail-${index}`;

          return (
            <li
              key={key}
              style={
                isTool
                  ? {
                      marginBottom: 6,
                      padding: '6px 8px',
                      borderLeft: '3px solid #5bc0de',
                      background: '#f4fafc',
                      fontFamily: 'Consolas, ui-monospace, monospace',
                      fontSize: 13,
                    }
                  : { marginBottom: 4 }
              }
            >
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'flex-start',
                  gap: 8,
                }}
              >
                <button
                  type="button"
                  id={toggleId}
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  aria-label={`${expanded ? 'Hide details' : 'Details'} for ${event.event_type} at ${formatTimestamp(event.timestamp)}`}
                  onClick={() => setExpandedEventKey(expanded ? null : key)}
                  style={{
                    flex: '0 0 auto',
                    cursor: 'pointer',
                    fontSize: 12,
                    padding: '2px 8px',
                    borderRadius: 2,
                    border: '1px solid #5bc0de',
                    background: expanded ? '#5bc0de' : '#fff',
                    color: expanded ? '#fff' : '#31708f',
                  }}
                >
                  {expanded ? 'Hide details' : 'Details'}
                </button>
                <span style={isTool ? { fontFamily: 'inherit' } : undefined}>
                  <strong>{formatTimestamp(event.timestamp)}</strong>
                  {' | '}
                  {event.phase || 'unscoped'}
                  {' | '}
                  {isTool ? (
                    <span style={{ color: '#31708f' }}>
                      <strong>{event.event_type}</strong>
                    </span>
                  ) : (
                    event.event_type
                  )}
                  {' | '}
                  {formatEventDetail(event)}
                </span>
              </div>
              {expanded ? (
                <div
                  id={panelId}
                  role="region"
                  aria-labelledby={toggleId}
                  style={{
                    marginTop: 10,
                    paddingTop: 8,
                    borderTop: '1px solid #bce8f1',
                  }}
                >
                  <EventDetailPanel event={event} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default RunTimeline;
