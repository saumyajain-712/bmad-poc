import type { RunTimelineEvent } from '../../services/bmadService';
import { TOOL_CALL_COMPLETED_EVENT_TYPE } from '../../services/bmadService';
import { formatRedactedJsonPretty } from './toolEventPresentation';

export type DetailRow = { label: string; value: string; emphasis?: 'error' };

/** Labeled rows for non-tool events (AC3). Always includes core identity; adds type-specific fields. */
export function getNonToolDetailRows(event: RunTimelineEvent): DetailRow[] {
  const rows: DetailRow[] = [
    { label: 'Timestamp', value: event.timestamp || '—' },
    { label: 'Phase', value: event.phase || '—' },
    { label: 'Event type', value: event.event_type },
  ];

  if (event.error_summary) {
    rows.push({ label: 'Error summary', value: event.error_summary, emphasis: 'error' });
  }

  if (event.event_type === 'phase-status-changed') {
    if (event.old_status !== undefined) rows.push({ label: 'Old status', value: String(event.old_status) });
    if (event.new_status !== undefined) rows.push({ label: 'New status', value: String(event.new_status) });
    if (event.reason) rows.push({ label: 'Reason', value: event.reason });
  } else if (event.previous_phase !== undefined || event.next_phase !== undefined) {
    if (event.previous_phase !== undefined) {
      rows.push({ label: 'Previous phase', value: String(event.previous_phase) });
    }
    if (event.next_phase !== undefined) rows.push({ label: 'Next phase', value: String(event.next_phase) });
    if (event.trigger) rows.push({ label: 'Trigger', value: event.trigger });
  } else if (event.context_source !== undefined || event.context_version !== undefined) {
    rows.push({ label: 'Context source', value: event.context_source ?? '—' });
    rows.push({
      label: 'Context version',
      value: event.context_version !== undefined ? String(event.context_version) : '—',
    });
  } else {
    if (event.reason) rows.push({ label: 'Reason', value: event.reason });
    if (event.old_status !== undefined) rows.push({ label: 'Old status', value: String(event.old_status) });
    if (event.new_status !== undefined) rows.push({ label: 'New status', value: String(event.new_status) });
    if (event.step) rows.push({ label: 'Step', value: event.step });
  }

  if (event.artifact && Object.keys(event.artifact).length > 0) {
    rows.push({ label: 'Artifact', value: formatRedactedJsonPretty(event.artifact) });
  }

  return rows;
}

export function isToolCallCompletedEvent(event: RunTimelineEvent): boolean {
  return event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE;
}

/** Full event JSON for support/debug (AC3); secrets redacted (AC4). */
export function formatFullEventForDebug(event: RunTimelineEvent): string {
  return formatRedactedJsonPretty(event);
}
