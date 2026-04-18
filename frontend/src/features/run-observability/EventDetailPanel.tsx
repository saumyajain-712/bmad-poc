import type { CSSProperties } from 'react';
import React from 'react';
import type { RunTimelineEvent } from '../../services/bmadService';
import { TOOL_CALL_COMPLETED_EVENT_TYPE } from '../../services/bmadService';
import {
  formatFullEventForDebug,
  getNonToolDetailRows,
  isToolCallCompletedEvent,
} from './eventDetailPresentation';
import { formatFullPayloadForDisplay } from './toolEventPresentation';

const detailPreStyle: CSSProperties = {
  margin: '6px 0 0',
  padding: 8,
  background: '#fff',
  border: '1px solid #bce8f1',
  borderRadius: 2,
  fontFamily: 'Consolas, ui-monospace, monospace',
  fontSize: 12,
  lineHeight: 1.45,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

const labelStyle: CSSProperties = {
  fontWeight: 600,
  color: '#31708f',
  marginTop: 8,
  marginBottom: 2,
};

const rowGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '120px 1fr',
  gap: '4px 10px',
  alignItems: 'start',
  fontSize: 13,
};

const EventDetailPanel: React.FC<{ event: RunTimelineEvent }> = ({ event }) => {
  if (isToolCallCompletedEvent(event)) {
    const name = event.tool_name || 'unknown_tool';
    const inputStr = formatFullPayloadForDisplay(event.tool_input ?? {});
    const outputStr = formatFullPayloadForDisplay(event.tool_output ?? {});

    return (
      <div data-testid="event-detail-panel">
        <div style={rowGridStyle}>
          <span style={{ fontWeight: 600 }}>Timestamp</span>
          <span>{event.timestamp || '—'}</span>
          <span style={{ fontWeight: 600 }}>Phase</span>
          <span>{event.phase || '—'}</span>
          <span style={{ fontWeight: 600 }}>Event type</span>
          <span>{TOOL_CALL_COMPLETED_EVENT_TYPE}</span>
          <span style={{ fontWeight: 600 }}>Tool</span>
          <span>{name}</span>
          {event.error_summary ? (
            <>
              <span style={{ fontWeight: 600, color: '#a94442' }}>Outcome / error</span>
              <span style={{ color: '#a94442' }}>{event.error_summary}</span>
            </>
          ) : null}
        </div>
        <div style={labelStyle}>Tool input</div>
        <pre style={detailPreStyle} data-testid="tool-input-full">
          {inputStr}
        </pre>
        <div style={labelStyle}>Tool output</div>
        <pre style={detailPreStyle} data-testid="tool-output-full">
          {outputStr}
        </pre>
      </div>
    );
  }

  const rows = getNonToolDetailRows(event);
  const debugDump = formatFullEventForDebug(event);

  return (
    <div data-testid="event-detail-panel">
      <div style={{ margin: 0 }}>
        {rows.map((row) => (
          <div key={row.label} style={{ marginBottom: row.label === 'Artifact' ? 6 : 4 }}>
            <div
              style={{
                fontWeight: 600,
                color: row.emphasis === 'error' ? '#a94442' : '#31708f',
                marginBottom: 2,
              }}
            >
              {row.label}
            </div>
            <div>
              {row.label === 'Artifact' || row.value.includes('\n') ? (
                <pre style={{ ...detailPreStyle, marginTop: 4 }}>{row.value}</pre>
              ) : (
                <span
                  style={row.emphasis === 'error' ? { color: '#a94442' } : undefined}
                  data-field={row.label.replace(/\s+/g, '-').toLowerCase()}
                >
                  {row.value}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div style={{ ...labelStyle, marginTop: 12 }}>Full event (debug)</div>
      <pre style={detailPreStyle} data-testid="full-event-json">
        {debugDump}
      </pre>
    </div>
  );
};

export default EventDetailPanel;
