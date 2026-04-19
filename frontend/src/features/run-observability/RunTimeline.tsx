import React, { useEffect, useState } from 'react';
import { TOOL_CALL_COMPLETED_EVENT_TYPE, type RunTimelineEvent } from '../../services/bmadService';
import EventDetailPanel from './EventDetailPanel';
import {
  classifyTimelineRowVariant,
  effectiveScopePhaseForRow,
  formatEventDetailForTimeline,
  getPhaseDisplayName,
  type TimelineRowVariant,
} from './phaseTimelinePresentation';

interface RunTimelineProps {
  events: RunTimelineEvent[];
}

function liStyleForVariant(variant: TimelineRowVariant, isTool: boolean): React.CSSProperties {
  if (variant === 'failure') {
    return {
      marginBottom: 6,
      padding: '6px 8px',
      borderLeft: '4px solid #a94442',
      background: '#fdf2f2',
      fontSize: 13,
    };
  }
  if (variant === 'tool' || isTool) {
    return {
      marginBottom: 6,
      padding: '6px 8px',
      borderLeft: '3px solid #5bc0de',
      background: '#f4fafc',
      fontFamily: 'Consolas, ui-monospace, monospace',
      fontSize: 13,
    };
  }
  if (variant === 'phase-transition') {
    return {
      marginBottom: 6,
      padding: '8px 10px',
      borderLeft: '4px solid #6f42c1',
      background: '#f3edff',
      fontSize: 13,
    };
  }
  if (variant === 'phase-governance') {
    return {
      marginBottom: 6,
      padding: '6px 8px',
      borderLeft: '3px solid #ec971f',
      background: '#fffbf2',
      fontSize: 13,
    };
  }
  if (variant === 'phase-status') {
    return {
      marginBottom: 6,
      padding: '6px 8px',
      borderLeft: '3px solid #5cb85c',
      background: '#f4faf7',
      fontSize: 13,
    };
  }
  return { marginBottom: 4 };
}

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

  // Single pass: working scope per row (phase-agnostic rows inherit prior scope; phase-transition uses next_phase).
  let scopeCarry: string | null = null;
  const rowScopes = events.map((event) => {
    const rowScope = effectiveScopePhaseForRow(event, scopeCarry);
    scopeCarry = rowScope;
    return rowScope;
  });

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
          const variant = classifyTimelineRowVariant(event);
          const rowScope = rowScopes[index] ?? null;
          const phaseScopeBoundary =
            index > 0 && rowScope !== rowScopes[index - 1];

          const expanded = expandedEventKey === key;
          const toggleId = `timeline-event-toggle-${index}`;
          const panelId = `timeline-event-detail-${index}`;
          const baseLi = liStyleForVariant(variant, isTool);
          const liStyles: React.CSSProperties = phaseScopeBoundary
            ? {
                ...baseLi,
                marginTop: 14,
                paddingTop: (baseLi.padding as string) || baseLi.paddingTop || 6,
                borderTop: '2px solid #cfd8dc',
              }
            : baseLi;

          return (
            <li
              key={key}
              data-timeline-variant={variant}
              data-phase-scope-boundary={phaseScopeBoundary ? 'true' : undefined}
              style={liStyles}
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
                  aria-label={`${expanded ? 'Hide details' : 'Details'} for ${variant === 'failure' ? 'failed ' : ''}${event.event_type} at ${formatTimestamp(event.timestamp)}`}
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
                  {getPhaseDisplayName(event.phase) === '—' ? 'unscoped' : getPhaseDisplayName(event.phase)}
                  {' | '}
                  {isTool ? (
                    <span style={{ color: variant === 'failure' ? '#a94442' : '#31708f' }}>
                      <strong>{event.event_type}</strong>
                    </span>
                  ) : variant === 'failure' ? (
                    <span style={{ color: '#a94442' }}>
                      <strong>{event.event_type}</strong>
                    </span>
                  ) : variant === 'phase-transition' ? (
                    <span style={{ color: '#5e2e9c' }}>
                      <strong>{event.event_type}</strong>
                    </span>
                  ) : variant === 'phase-governance' || variant === 'phase-status' ? (
                    <span style={{ color: '#555' }}>
                      <strong>{event.event_type}</strong>
                    </span>
                  ) : (
                    event.event_type
                  )}
                  {' | '}
                  {formatEventDetailForTimeline(event)}
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
